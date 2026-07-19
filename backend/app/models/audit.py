"""Audit log for sensitive state changes.

Records who did what to which record, for the actions where "it used to say
something else" is a question someone will eventually ask: an application's
status changing, and a posting being deleted along with everyone who applied
to it.

Append-only by convention — nothing in the application updates or deletes a row
here. The actor is nullable and the entity is stored as a type/id pair rather
than a foreign key, deliberately: a log entry has to outlive the thing it
describes, and a FK to a deleted job would either block the delete or cascade
the evidence away with it.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ENTITY_TYPE_MAX_LENGTH = 40
SUMMARY_MAX_LENGTH = 500


class AuditAction(StrEnum):
    """What happened. A closed set, so the log stays queryable."""

    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"
    JOB_DELETED = "JOB_DELETED"
    JOB_PUBLISHED = "JOB_PUBLISHED"
    JOB_UNPUBLISHED = "JOB_UNPUBLISHED"
    APPLICANT_CONTACTED = "APPLICANT_CONTACTED"


class AuditLogEntry(Base):
    """One recorded action."""

    __tablename__ = "audit_log"

    __table_args__ = (
        # The two questions actually asked of a log: what happened to this
        # record, and what did this person do.
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # SET NULL, not CASCADE: deleting an account must not erase what it did.
    # The entry keeps its actor_email so the record survives the user row.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(254), nullable=False)

    action: Mapped[AuditAction] = mapped_column(
        String(ENTITY_TYPE_MAX_LENGTH), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(ENTITY_TYPE_MAX_LENGTH), nullable=False
    )
    # No foreign key on purpose — see the module docstring.
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Human-readable, e.g. "SUBMITTED -> ACCEPTED". Enough to answer the
    # question without joining anything back that may no longer exist.
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        """Identifies the entry without dumping the summary."""
        return (
            f"<AuditLogEntry {self.action} {self.entity_type}={self.entity_id} "
            f"by={self.actor_email}>"
        )
