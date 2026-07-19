"""Job posting rules.

Visibility and ownership are decided here rather than in the handlers, so every
caller — the API today, a background job or CLI later — gets the same answer to
"may this person see or change this posting?".
"""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.job import EmploymentType, Job
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobUpdate


class JobNotFoundError(Exception):
    """Raised when a posting does not exist, or must appear not to.

    Deliberately covers both. Returning a distinct "forbidden" for a posting
    that exists but belongs to someone else would confirm its existence, which
    is enough to enumerate another account's postings by id.
    """


def _visible_to(viewer: User | None) -> Select[tuple[Job]]:
    """Base query restricted to what this viewer is allowed to see.

    Anonymous visitors and candidates see published postings only. An HR user
    additionally sees their own drafts — but still not anyone else's.
    """
    statement = select(Job)

    if viewer is not None and viewer.role is UserRole.HR:
        return statement.where(
            (Job.is_published.is_(True)) | (Job.created_by_id == viewer.id)
        )

    return statement.where(Job.is_published.is_(True))


def list_jobs(
    db: Session,
    *,
    viewer: User | None = None,
    search: str | None = None,
    company: str | None = None,
    location: str | None = None,
    employment_type: EmploymentType | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    """Return one page of visible postings, newest first, plus the total.

    Filters combine with AND, which is what someone narrowing a list expects:
    each one they add should show fewer results, never more.
    """
    statement = _visible_to(viewer)

    if search:
        # ilike rather than lower(...) like: the candidate typing "engineer"
        # should match "Backend Engineer" regardless of case.
        statement = statement.where(Job.title.ilike(f"%{search}%"))

    if company:
        # Substring like the others: "acme" should find "Acme Robotics Ltd".
        statement = statement.where(Job.company.ilike(f"%{company}%"))

    if location:
        # Substring, not equality: "berlin" should find "Berlin, Germany", and
        # nobody types a location exactly as it was entered.
        statement = statement.where(Job.location.ilike(f"%{location}%"))

    if employment_type is not None:
        # Exact — it is a closed enum, so a partial match would be meaningless.
        statement = statement.where(Job.employment_type == employment_type)

    total = db.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()

    page = statement.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    jobs = list(db.execute(page).scalars().unique().all())

    return jobs, total


def list_jobs_owned_by(
    db: Session, *, owner: User, limit: int, offset: int
) -> tuple[list[Job], int]:
    """Return the postings this HR user authored, drafts included."""
    statement = select(Job).where(Job.created_by_id == owner.id)

    total = db.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()

    page = statement.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    jobs = list(db.execute(page).scalars().unique().all())

    return jobs, total


def get_visible_job(db: Session, job_id: uuid.UUID, *, viewer: User | None) -> Job:
    """Return a posting the viewer may see, or raise JobNotFoundError."""
    job = db.execute(_visible_to(viewer).where(Job.id == job_id)).scalar_one_or_none()

    if job is None:
        raise JobNotFoundError(job_id)

    return job


def get_owned_job(db: Session, job_id: uuid.UUID, *, owner: User) -> Job:
    """Return a posting this user owns, or raise JobNotFoundError.

    The ownership predicate is part of the query rather than a check after
    loading: there is then no window in which code holds a row it is not
    entitled to, and no branch that could forget to test it.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.created_by_id == owner.id)
    ).scalar_one_or_none()

    if job is None:
        raise JobNotFoundError(job_id)

    return job


def create_job(db: Session, *, payload: JobCreate, owner: User) -> Job:
    """Create a posting owned by the given HR user.

    Fields are assigned explicitly rather than by unpacking the payload, so a
    field added to the schema later cannot silently become writable here.
    """
    job = Job(
        title=payload.title,
        company=payload.company,
        description=payload.description,
        location=payload.location,
        employment_type=payload.employment_type,
        is_published=payload.is_published,
        created_by_id=owner.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, *, job: Job, payload: JobUpdate) -> Job:
    """Apply a partial edit.

    exclude_unset is what makes PATCH partial: without it, every field the
    caller omitted would arrive as None and blank the stored value.
    """
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, *, job: Job) -> None:
    """Remove a posting."""
    db.delete(job)
    db.commit()
