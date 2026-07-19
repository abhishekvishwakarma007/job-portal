"""Job posting routes: HR create/update/delete, public browse.

Two distinct authorisation shapes live here, and the difference is deliberate:

- reaching a management endpoint at all requires an HR account, and a candidate
  who tries gets 403 — the endpoint's existence is already public in the
  OpenAPI schema, so there is nothing to hide
- reaching a *particular posting* you do not own gets 404, not 403, because a
  403 would confirm the row exists and let someone map another account's
  postings by trying ids
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import HRUser, OptionalUser
from app.db.session import get_db
from app.models.job import EmploymentType
from app.schemas.application import ApplicationPage, ApplicationRead
from app.schemas.job import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    JobCreate,
    JobPage,
    JobRead,
    JobUpdate,
)
from app.services.application import (
    ApplicationNotFoundError,
    list_applications_for_job,
)
from app.services.job import (
    JobNotFoundError,
    create_job,
    delete_job,
    get_owned_job,
    get_visible_job,
    list_jobs,
    list_jobs_owned_by,
    update_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

_JOB_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Job not found",
)

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, Query(ge=0)]


@router.get("", response_model=JobPage, summary="Browse published jobs")
def browse_jobs(
    db: Annotated[Session, Depends(get_db)],
    viewer: OptionalUser,
    search: Annotated[str | None, Query(max_length=200)] = None,
    location: Annotated[str | None, Query(max_length=120)] = None,
    employment_type: EmploymentType | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> JobPage:
    """List published postings, newest first, optionally filtered.

    Public: candidates need to see what is on offer before creating an account.
    An HR user calling this also sees their own drafts, which is why the caller
    is resolved optionally rather than required.

    `search` matches the title, `location` matches the location, and both are
    substring and case-insensitive. `employment_type` is exact, being a closed
    enum. Filters combine with AND.
    """
    jobs, total = list_jobs(
        db,
        viewer=viewer,
        search=search,
        location=location,
        employment_type=employment_type,
        limit=limit,
        offset=offset,
    )

    return JobPage(
        items=[JobRead.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/mine", response_model=JobPage, summary="Jobs you posted")
def list_my_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> JobPage:
    """List the caller's own postings, drafts included.

    Declared before /{job_id} so the literal segment wins the route match —
    otherwise "mine" would be parsed as a job id and 422 on the UUID.
    """
    jobs, total = list_jobs_owned_by(db, owner=current_user, limit=limit, offset=offset)

    return JobPage(
        items=[JobRead.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post a job",
)
def post_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
) -> JobRead:
    """Create a posting owned by the authenticated HR user."""
    job = create_job(db, payload=payload, owner=current_user)

    return JobRead.model_validate(job)


@router.get("/{job_id}", response_model=JobRead, summary="Read a job")
def read_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: OptionalUser,
) -> JobRead:
    """Return a posting the caller is allowed to see.

    An unpublished posting is a 404 to everyone but its author — a draft should
    not be discoverable, and 403 would announce that it exists.
    """
    try:
        job = get_visible_job(db, job_id, viewer=viewer)
    except JobNotFoundError as exc:
        raise _JOB_NOT_FOUND from exc

    return JobRead.model_validate(job)


@router.patch("/{job_id}", response_model=JobRead, summary="Edit a job you posted")
def edit_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
) -> JobRead:
    """Apply a partial edit to the caller's own posting."""
    try:
        job = get_owned_job(db, job_id, owner=current_user)
    except JobNotFoundError as exc:
        raise _JOB_NOT_FOUND from exc

    return JobRead.model_validate(update_job(db, job=job, payload=payload))


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job you posted",
)
def remove_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
) -> Response:
    """Delete the caller's own posting."""
    try:
        job = get_owned_job(db, job_id, owner=current_user)
    except JobNotFoundError as exc:
        raise _JOB_NOT_FOUND from exc

    delete_job(db, job=job)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{job_id}/applications",
    response_model=ApplicationPage,
    summary="Applications to a job you posted",
)
def list_job_applications(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> ApplicationPage:
    """Return the pipeline for a posting the caller owns.

    404 when the job belongs to someone else, for the usual reason: a 403 would
    confirm the posting exists and hint at how much interest it has attracted.
    """
    try:
        applications, total = list_applications_for_job(
            db, job_id=job_id, owner=current_user, limit=limit, offset=offset
        )
    except ApplicationNotFoundError as exc:
        raise _JOB_NOT_FOUND from exc

    return ApplicationPage(
        items=[ApplicationRead.model_validate(item) for item in applications],
        total=total,
        limit=limit,
        offset=offset,
    )
