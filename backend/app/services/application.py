"""Application rules.

Who may see or change an application is decided here. Two people have a
legitimate claim on one row — the candidate who wrote it and the HR user who
owns the job — and they are allowed different things, so the two access paths
are separate functions rather than one function with a role branch.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditAction
from app.models.job import Job
from app.models.user import User
from app.services import audit


class ApplicationNotFoundError(Exception):
    """Raised when an application does not exist, or must appear not to.

    Covers both cases deliberately: telling one candidate that another's
    application exists but is forbidden would leak who has applied where.
    """


class AlreadyAppliedError(Exception):
    """Raised when the candidate already holds an application for this job."""


class JobNotOpenError(Exception):
    """Raised when the job is absent or not accepting applications.

    One exception for both, so an unpublished draft is indistinguishable from
    a job that does not exist.
    """


def create_application(
    db: Session, *, job_id: uuid.UUID, cover_letter: str, candidate: User
) -> Application:
    """Submit an application to a published job.

    The duplicate check is the composite UNIQUE constraint rather than a
    preceding SELECT: two concurrent submissions could both pass a
    check-then-insert and both commit, putting one person in the pipeline
    twice. The IntegrityError is the authoritative answer.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.is_published.is_(True))
    ).scalar_one_or_none()

    if job is None:
        raise JobNotOpenError(job_id)

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        cover_letter=cover_letter,
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(application)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AlreadyAppliedError(job_id) from exc

    db.refresh(application)
    return application


def list_applications_by_candidate(
    db: Session, *, candidate: User, limit: int, offset: int
) -> tuple[list[Application], int]:
    """Return the applications this candidate submitted, newest first."""
    statement = select(Application).where(Application.candidate_id == candidate.id)

    total = db.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()

    page = statement.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    applications = list(db.execute(page).scalars().unique().all())

    return applications, total


def list_applications_for_job(
    db: Session, *, job_id: uuid.UUID, owner: User, limit: int, offset: int
) -> tuple[list[Application], int]:
    """Return one job's pipeline, for the HR user who owns that job.

    Ownership is joined into the query rather than checked separately, so a
    pipeline can never be returned for a job the caller does not own.
    """
    owns_job = db.execute(
        select(Job.id).where(Job.id == job_id, Job.created_by_id == owner.id)
    ).scalar_one_or_none()

    if owns_job is None:
        raise ApplicationNotFoundError(job_id)

    statement = select(Application).where(Application.job_id == job_id)

    total = db.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()

    page = statement.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    applications = list(db.execute(page).scalars().unique().all())

    return applications, total


def get_application_for_candidate(
    db: Session, application_id: uuid.UUID, *, candidate: User
) -> Application:
    """Return an application this candidate authored."""
    application = db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.candidate_id == candidate.id,
        )
    ).scalar_one_or_none()

    if application is None:
        raise ApplicationNotFoundError(application_id)

    return application


def get_application_for_job_owner(
    db: Session, application_id: uuid.UUID, *, owner: User
) -> Application:
    """Return an application on a job this HR user owns.

    The join to Job is what enforces it: an HR user reaching an application on
    someone else's posting matches no row and gets the same not-found answer as
    an id that was never issued.
    """
    application = db.execute(
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id, Job.created_by_id == owner.id)
    ).scalar_one_or_none()

    if application is None:
        raise ApplicationNotFoundError(application_id)

    return application


def update_application_status(
    db: Session,
    *,
    application: Application,
    status: ApplicationStatus,
    actor: User,
) -> Application:
    """Move an application to a new pipeline state, recording who moved it.

    A rejection someone disputes is exactly the case an audit trail exists
    for, so the previous state is captured in the entry rather than left to be
    inferred.

    The entry shares this transaction: if the update rolls back, so does the
    log, and the log never claims a change that did not happen.
    """
    previous = application.status
    application.status = status

    audit.record(
        db,
        actor=actor,
        action=AuditAction.APPLICATION_STATUS_CHANGED,
        entity_type="application",
        entity_id=application.id,
        summary=f"{previous.value} -> {status.value}",
    )

    db.commit()
    db.refresh(application)
    return application
