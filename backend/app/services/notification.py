"""Creating and reading in-app notifications.

The "send email" action writes one of these rather than dispatching mail. See
app/models/notification.py for why.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.audit import AuditAction
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from app.services import audit


class NotificationNotFoundError(Exception):
    """Raised when a notification does not exist or belongs to someone else."""


def notify_applicant(
    db: Session, *, application: Application, job: Job, sender: User, message: str
) -> Notification:
    """Record a message from an HR user to an applicant.

    The recipient is taken from the application rather than the request body,
    so an HR user cannot address a message to someone who did not apply.
    """
    notification = Notification(
        user_id=application.candidate_id,
        subject=f"Update on your application for {job.title}",
        body=(f"{message}\n\n" f"— {sender.full_name}, {job.company}"),
        job_id=job.id,
    )
    db.add(notification)

    # A message sent in the company's name to someone who applied — sensitive
    # enough to want a record of who sent it and to whom.
    audit.record(
        db,
        actor=sender,
        action=AuditAction.APPLICANT_CONTACTED,
        entity_type="application",
        entity_id=application.id,
        summary=f"Messaged {application.candidate_id} about {job.title!r}",
    )

    db.commit()
    db.refresh(notification)

    return notification


def list_notifications(
    db: Session, *, user: User, limit: int, offset: int
) -> tuple[list[Notification], int]:
    """Return one page of a user's notifications, newest first."""
    statement = select(Notification).where(Notification.user_id == user.id)

    total = db.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()

    page = statement.order_by(Notification.created_at.desc()).limit(limit).offset(offset)

    return list(db.execute(page).scalars().all()), total


def count_unread(db: Session, *, user: User) -> int:
    """How many unread messages this user has, for the header badge."""
    return db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ).scalar_one()


def dismiss(db: Session, notification_id: uuid.UUID, *, user: User) -> None:
    """Delete one of the caller's own notifications.

    Ownership is in the query rather than checked afterwards, so another
    user's notification is not found rather than found-and-refused — and there
    is no window in which this holds a row it may not delete.
    """
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    ).scalar_one_or_none()

    if notification is None:
        raise NotificationNotFoundError(notification_id)

    db.delete(notification)
    db.commit()


def mark_read(db: Session, notification_id: uuid.UUID, *, user: User) -> Notification:
    """Mark one of the caller's own notifications as read.

    Ownership is in the query rather than checked afterwards, so another user's
    notification is not found rather than found-and-refused.
    """
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    ).scalar_one_or_none()

    if notification is None:
        raise NotificationNotFoundError(notification_id)

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)

    return notification
