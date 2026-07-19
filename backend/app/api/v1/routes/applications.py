"""Application routes: candidate apply and list, HR review and status updates.

Reading one application has two legitimate callers with different rights — the
candidate who wrote it and the HR user who owns the job — so the handler
dispatches on role rather than trying to express both in one query.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CandidateUser, CurrentUser, HRUser
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.application import (
    ApplicationCreate,
    ApplicationPage,
    ApplicationRead,
    ApplicationStatusUpdate,
)
from app.schemas.job import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.notification import ContactApplicantRequest, NotificationRead
from app.services.application import (
    AlreadyAppliedError,
    ApplicationNotFoundError,
    JobNotOpenError,
    create_application,
    get_application_for_candidate,
    get_application_for_job_owner,
    list_applications_by_candidate,
    update_application_status,
)
from app.services.notification import notify_applicant

router = APIRouter(prefix="/applications", tags=["applications"])

_APPLICATION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Application not found",
)

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, Query(ge=0)]


@router.post(
    "",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Apply to a job",
)
def apply_to_job(
    payload: ApplicationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: CandidateUser,
) -> ApplicationRead:
    """Submit an application to a published job.

    409 when the candidate already applied. An unpublished or absent job is
    404 either way — a draft should not be discoverable by trying to apply
    to it.
    """
    try:
        application = create_application(
            db,
            job_id=payload.job_id,
            cover_letter=payload.cover_letter,
            candidate=current_user,
        )
    except JobNotOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
    except AlreadyAppliedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this job",
        ) from exc

    return ApplicationRead.model_validate(application)


@router.get("/mine", response_model=ApplicationPage, summary="Your applications")
def list_my_applications(
    db: Annotated[Session, Depends(get_db)],
    current_user: CandidateUser,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> ApplicationPage:
    """List the caller's own applications, newest first."""
    applications, total = list_applications_by_candidate(
        db, candidate=current_user, limit=limit, offset=offset
    )

    return ApplicationPage(
        items=[ApplicationRead.model_validate(item) for item in applications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationRead,
    summary="Read an application",
)
def read_application(
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
) -> ApplicationRead:
    """Return an application the caller is entitled to see.

    A candidate may read their own; an HR user may read any on a job they own.
    Everyone else gets 404 rather than 403 — telling one candidate that
    another's application exists would leak who applied where.
    """
    try:
        if current_user.role is UserRole.HR:
            application = get_application_for_job_owner(
                db, application_id, owner=current_user
            )
        else:
            application = get_application_for_candidate(
                db, application_id, candidate=current_user
            )
    except ApplicationNotFoundError as exc:
        raise _APPLICATION_NOT_FOUND from exc

    return ApplicationRead.model_validate(application)


@router.patch(
    "/{application_id}",
    response_model=ApplicationRead,
    summary="Move an application through the pipeline",
)
def set_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
) -> ApplicationRead:
    """Update the status of an application on a job the caller owns.

    HR-only: a candidate able to set their own status could accept themselves.
    """
    try:
        application = get_application_for_job_owner(
            db, application_id, owner=current_user
        )
    except ApplicationNotFoundError as exc:
        raise _APPLICATION_NOT_FOUND from exc

    updated = update_application_status(
        db, application=application, status=payload.status, actor=current_user
    )

    return ApplicationRead.model_validate(updated)


@router.post(
    "/{application_id}/contact",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Message an applicant",
)
def contact_applicant(
    application_id: uuid.UUID,
    payload: ContactApplicantRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: HRUser,
) -> NotificationRead:
    """Send an applicant a message about their application.

    No mail is dispatched. The message is written as an in-app notification the
    candidate reads in the portal, which keeps a review environment from
    emitting real email to a real inbox. A production build would keep this row
    as the record and add a sender alongside it.

    Only the owner of the posting may write to its applicants, and the
    recipient comes from the application rather than the request body — so a
    message cannot be addressed to someone who never applied.
    """
    try:
        application = get_application_for_job_owner(
            db, application_id, owner=current_user
        )
    except ApplicationNotFoundError as exc:
        raise _APPLICATION_NOT_FOUND from exc

    notification = notify_applicant(
        db,
        application=application,
        job=application.job,
        sender=current_user,
        message=payload.message,
    )

    return NotificationRead.model_validate(notification)
