"""Audit log.

The point of a log is that it is still true later, so these concentrate on the
cases where the thing being described has changed or gone: a deleted job, a
deleted actor, and a change that rolled back.
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditAction, AuditLogEntry
from app.models.job import EmploymentType, Job
from app.models.user import User, UserRole
from app.schemas.job import JobUpdate
from app.services import audit
from app.services.application import update_application_status
from app.services.auth import register_user
from app.services.job import delete_job, update_job
from app.services.notification import notify_applicant

PASSWORD = "Str0ng@Password"


@pytest.fixture
def hr_user(db_session: Session) -> User:
    """The actor."""
    return register_user(
        db_session,
        email="hr@test.com",
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )


@pytest.fixture
def candidate(db_session: Session) -> User:
    """The applicant."""
    return register_user(
        db_session,
        email="candidate@test.com",
        password=PASSWORD,
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    )


@pytest.fixture
def job(db_session: Session, hr_user: User) -> Job:
    """A posting owned by hr_user."""
    posting = Job(
        title="Senior Platform Engineer",
        company="Northwind Labs",
        description="Own the deployment pipeline.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        created_by_id=hr_user.id,
    )
    db_session.add(posting)
    db_session.commit()
    db_session.refresh(posting)
    return posting


@pytest.fixture
def application(db_session: Session, job: Job, candidate: User) -> Application:
    """An application to that posting."""
    submitted = Application(
        job_id=job.id, candidate_id=candidate.id, cover_letter="Pipeline work."
    )
    db_session.add(submitted)
    db_session.commit()
    db_session.refresh(submitted)
    return submitted


def test_status_change_is_recorded(
    db_session: Session, application: Application, hr_user: User
) -> None:
    """Who moved it, and from what."""
    update_application_status(
        db_session,
        application=application,
        status=ApplicationStatus.ACCEPTED,
        actor=hr_user,
    )

    entries = audit.entries_for(
        db_session, entity_type="application", entity_id=application.id
    )

    assert len(entries) == 1
    assert entries[0].action == AuditAction.APPLICATION_STATUS_CHANGED
    assert entries[0].actor_email == hr_user.email


def test_status_change_records_the_previous_value(
    db_session: Session, application: Application, hr_user: User
) -> None:
    """A disputed rejection is the case this exists for.

    Recording only the new state would leave "what did it say before?"
    unanswerable, which is the question actually asked.
    """
    update_application_status(
        db_session,
        application=application,
        status=ApplicationStatus.REJECTED,
        actor=hr_user,
    )

    entry = audit.entries_for(
        db_session, entity_type="application", entity_id=application.id
    )[0]

    assert entry.summary == "SUBMITTED -> REJECTED"


def test_successive_changes_build_a_history(
    db_session: Session, application: Application, hr_user: User
) -> None:
    """Ordered oldest first, because a history reads forwards."""
    for status in (ApplicationStatus.UNDER_REVIEW, ApplicationStatus.ACCEPTED):
        update_application_status(
            db_session, application=application, status=status, actor=hr_user
        )

    summaries = [
        entry.summary
        for entry in audit.entries_for(
            db_session, entity_type="application", entity_id=application.id
        )
    ]

    assert summaries == ["SUBMITTED -> UNDER_REVIEW", "UNDER_REVIEW -> ACCEPTED"]


def test_job_deletion_is_recorded(db_session: Session, job: Job, hr_user: User) -> None:
    """Deleting a posting destroys other people's applications with it."""
    job_id = job.id

    delete_job(db_session, job=job, actor=hr_user)

    entries = audit.entries_for(db_session, entity_type="job", entity_id=job_id)

    assert len(entries) == 1
    assert entries[0].action == AuditAction.JOB_DELETED


def test_the_entry_survives_the_job_it_describes(
    db_session: Session, job: Job, hr_user: User
) -> None:
    """The decisive property.

    entity_id carries no foreign key precisely so this works — a FK would have
    cascaded the evidence away with the record, which is the opposite of what a
    log is for.
    """
    job_id = job.id
    title = job.title

    delete_job(db_session, job=job, actor=hr_user)

    assert db_session.query(Job).count() == 0
    entry = audit.entries_for(db_session, entity_type="job", entity_id=job_id)[0]
    assert title in entry.summary


def test_the_entry_survives_the_actor(
    db_session: Session, job: Job, hr_user: User
) -> None:
    """Deleting an account must not erase what it did.

    actor_id nulls out, but actor_email was copied at write time, so the entry
    still names who acted.
    """
    job_id = job.id
    actor_email = hr_user.email

    delete_job(db_session, job=job, actor=hr_user)
    db_session.delete(hr_user)
    db_session.commit()

    entry = audit.entries_for(db_session, entity_type="job", entity_id=job_id)[0]

    assert entry.actor_id is None
    assert entry.actor_email == actor_email


def test_a_rolled_back_change_leaves_no_entry(
    db_session: Session, application: Application, hr_user: User
) -> None:
    """The log shares the caller's transaction, so it cannot over-report.

    An entry written outside the transaction would claim a change that never
    landed — worse than no log, because it would be believed.
    """
    audit.record(
        db_session,
        actor=hr_user,
        action=AuditAction.APPLICATION_STATUS_CHANGED,
        entity_type="application",
        entity_id=application.id,
        summary="SUBMITTED -> ACCEPTED",
    )
    db_session.rollback()

    assert db_session.query(AuditLogEntry).count() == 0


def test_entries_are_scoped_to_their_entity(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """One record's history must not include another's."""
    update_application_status(
        db_session,
        application=application,
        status=ApplicationStatus.ACCEPTED,
        actor=hr_user,
    )

    assert audit.entries_for(db_session, entity_type="job", entity_id=job.id) == []


def test_publishing_is_recorded(db_session: Session, hr_user: User) -> None:
    """Visibility changes decide who can see a posting, so they are audited."""
    draft = Job(
        title="Engineering Manager",
        company="Northwind Labs",
        description="Not advertised yet.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        is_published=False,
        created_by_id=hr_user.id,
    )
    db_session.add(draft)
    db_session.commit()

    update_job(db_session, job=draft, payload=JobUpdate(is_published=True), actor=hr_user)

    entries = audit.entries_for(db_session, entity_type="job", entity_id=draft.id)

    assert [entry.action for entry in entries] == [AuditAction.JOB_PUBLISHED]


def test_unpublishing_is_recorded(db_session: Session, job: Job, hr_user: User) -> None:
    """The other direction of the same decision."""
    update_job(db_session, job=job, payload=JobUpdate(is_published=False), actor=hr_user)

    entries = audit.entries_for(db_session, entity_type="job", entity_id=job.id)

    assert [entry.action for entry in entries] == [AuditAction.JOB_UNPUBLISHED]


def test_editing_wording_is_not_recorded(
    db_session: Session, job: Job, hr_user: User
) -> None:
    """Only visibility is audited, not every keystroke.

    Logging ordinary edits would bury the changes that matter in noise, which
    is how audit logs stop being read.
    """
    update_job(
        db_session, job=job, payload=JobUpdate(title="Staff Engineer"), actor=hr_user
    )

    assert audit.entries_for(db_session, entity_type="job", entity_id=job.id) == []


def test_republishing_an_already_published_job_records_nothing(
    db_session: Session, job: Job, hr_user: User
) -> None:
    """A no-op change is not an event.

    The field being present in the payload is not the same as it changing, and
    recording the former would log every save of an unchanged checkbox.
    """
    update_job(db_session, job=job, payload=JobUpdate(is_published=True), actor=hr_user)

    assert audit.entries_for(db_session, entity_type="job", entity_id=job.id) == []


def test_contacting_an_applicant_is_recorded(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """A message sent in the company name to someone who applied."""
    notify_applicant(
        db_session,
        application=application,
        job=job,
        sender=hr_user,
        message="We would like to invite you to a first interview.",
    )

    entries = audit.entries_for(
        db_session, entity_type="application", entity_id=application.id
    )

    assert [entry.action for entry in entries] == [AuditAction.APPLICANT_CONTACTED]
    assert entries[0].actor_email == hr_user.email


def test_every_declared_action_has_a_call_site() -> None:
    """Guards against the enum advertising coverage that does not exist.

    Three members were previously declared and never recorded, so the type
    claimed more audit coverage than the code delivered. This fails if that
    happens again.
    """
    # Anchored to this file, not the working directory: an autouse fixture
    # runs every test from a temp directory, so a relative path finds nothing
    # and the assertion would pass by scanning zero files.
    app_root = Path(__file__).resolve().parent.parent / "app"
    declaration = app_root / "models" / "audit.py"

    recorded: set[AuditAction] = set()

    for path in app_root.rglob("*.py"):
        if path == declaration:
            continue

        text = path.read_text(encoding="utf-8")
        recorded.update(
            action for action in AuditAction if f"AuditAction.{action.name}" in text
        )

    assert recorded == set(
        AuditAction
    ), f"declared but never recorded: {set(AuditAction) - recorded}"
