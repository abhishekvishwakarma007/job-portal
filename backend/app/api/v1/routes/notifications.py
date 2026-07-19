"""In-app notification routes.

Notifications stand in for email: an HR user contacting an applicant writes a
row, and the candidate reads it here. Nothing is dispatched — see
app/models/notification.py for why.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.schemas.job import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.notification import NotificationPage, NotificationRead
from app.services.notification import (
    NotificationNotFoundError,
    count_unread,
    dismiss,
    list_notifications,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/mine", response_model=NotificationPage, summary="Your notifications")
def list_my_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> NotificationPage:
    """Return the caller's own notifications, newest first."""
    items, total = list_notifications(db, user=current_user, limit=limit, offset=offset)

    return NotificationPage(
        items=[NotificationRead.model_validate(item) for item in items],
        total=total,
        unread=count_unread(db, user=current_user),
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a notification read",
)
def read_notification(
    notification_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
) -> NotificationRead:
    """Mark one of the caller's own notifications as read.

    404 for someone else's, rather than 403: whether a given notification id
    exists is not something one user should learn about another.
    """
    try:
        notification = mark_read(db, notification_id, user=current_user)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        ) from exc

    return NotificationRead.model_validate(notification)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss a notification",
)
def dismiss_notification(
    notification_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
) -> Response:
    """Remove one of the caller's own notifications.

    404 for someone else's, matching the read endpoint: whether a given
    notification id exists is not something one user should learn about
    another.
    """
    try:
        dismiss(db, notification_id, user=current_user)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
