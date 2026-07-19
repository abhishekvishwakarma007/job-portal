"""In-app notification model.

Stands in for email. Nothing is actually sent: an HR user "contacting" a
candidate writes a row here, and the candidate reads it in the app. That keeps
the demo self-contained — no SMTP credentials, no outbound mail from a review
environment, and no chance of a real message reaching a real inbox.

A production build would keep this table as the in-app inbox and add a mail
sender alongside it, so the row remains the record of what was sent.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SUBJECT_MAX_LENGTH = 200


class Notification(Base):
    """A message delivered to one user inside the app."""

    __tablename__ = "notifications"

    __table_args__ = (
        # The inbox query: this user's messages, newest first, unread counted.
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # The recipient. CASCADE because a message to a deleted account is
    # unreachable by definition.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(SUBJECT_MAX_LENGTH), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    # SET NULL, not CASCADE: deleting a posting should not erase the record
    # that someone was contacted about it.
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """Identifies the row without dumping the body."""
        return f"<Notification id={self.id} user={self.user_id} read={self.is_read}>"
