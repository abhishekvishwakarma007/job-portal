"""Job posting model.

A job belongs to the HR user who created it. That ownership is what every
management check keys off: an HR user may edit their own postings and nobody
else's, so the foreign key is the authorisation boundary rather than a
convenience for joins.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User

TITLE_MAX_LENGTH = 200
LOCATION_MAX_LENGTH = 120
COMPANY_MAX_LENGTH = 120


class EmploymentType(StrEnum):
    """How the role is engaged. A closed set so filters stay meaningful."""

    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"


class Job(Base):
    """A posting created by an HR user.

    `is_published` is the visibility switch: candidates only ever see published
    postings, so an unpublished draft must be invisible to them entirely — not
    merely non-applicable.
    """

    __tablename__ = "jobs"

    __table_args__ = (
        # Candidates browse published jobs newest-first, which is otherwise a
        # full scan plus a sort once the table is more than trivially sized.
        Index("ix_jobs_published_created_at", "is_published", "created_at"),
        # Company is a browse filter; an unindexed ILIKE over it scans every row.
        Index("ix_jobs_company", "company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)
    # Stored on the posting rather than derived from the HR account: one
    # recruiter can hire for several companies, and the account name is who
    # posted it, not who the role is with.
    company: Mapped[str] = mapped_column(
        String(COMPANY_MAX_LENGTH),
        nullable=False,
        server_default="Confidential",
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(LOCATION_MAX_LENGTH), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(
            EmploymentType,
            name="employment_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    # No standalone index: the composite in __table_args__ leads with this
    # column, so Postgres can serve an is_published-only lookup from it. A
    # second index would cost write throughput and buy nothing.
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    # ondelete CASCADE: removing an HR account must not leave postings behind
    # pointing at a user that no longer exists.
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    created_by: Mapped[User] = relationship(lazy="joined")

    def __repr__(self) -> str:
        """Identifies the row without dumping the full description."""
        return f"<Job id={self.id} title={self.title!r} published={self.is_published}>"
