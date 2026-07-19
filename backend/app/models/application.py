"""Job application model.

One candidate may hold at most one application per job. That is enforced by a
composite UNIQUE constraint rather than a service-layer check, because two
concurrent submissions could both pass a check-then-insert and both commit —
leaving one person in a job's pipeline twice.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.job import Job
from app.models.user import User

COVER_LETTER_MAX_LENGTH = 5_000


class ApplicationStatus(StrEnum):
    """Where an application sits in the HR pipeline.

    A closed set so the UI can render every state and no free-text status can
    appear that the frontend has no rendering for.
    """

    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class Application(Base):
    """A candidate's application to one job."""

    __tablename__ = "applications"

    __table_args__ = (
        # The duplicate-apply backstop. A service-layer check alone loses the
        # race between two concurrent submissions; this cannot.
        UniqueConstraint("job_id", "candidate_id", name="uq_applications_job_candidate"),
        # HR reviews one job's pipeline newest-first; candidates list their own.
        Index("ix_applications_job_created_at", "job_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # CASCADE on both sides: an application is meaningless once either the job
    # or the candidate is gone, and a dangling row would break every join.
    # No standalone index: the composite in __table_args__ leads with this
    # column, so a job_id-only lookup is served from it.
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ApplicationStatus.SUBMITTED,
        server_default=ApplicationStatus.SUBMITTED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped[Job] = relationship(lazy="joined")
    candidate: Mapped[User] = relationship(lazy="joined")

    def __repr__(self) -> str:
        """Identifies the row without dumping the cover letter."""
        return (
            f"<Application id={self.id} job={self.job_id} "
            f"candidate={self.candidate_id} status={self.status}>"
        )
