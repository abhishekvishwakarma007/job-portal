"""Candidate profile.

One row per candidate, holding the sections a job site asks for: career
preferences, a summary, key skills, employment history, education, and
personal details.

Modelled as a single row with text columns rather than separate tables for
employment and education. That is a deliberate trade for this scope: the app
never queries "everyone who worked at X", only ever renders a whole profile at
once, and one row keeps reads to a single fetch with no joins. Splitting them
out is the right move the moment either becomes searchable on its own.

`key_skills` is the exception that carries real weight — it feeds the applicant
ranking, so it is stored as a normalised comma-separated list rather than free
prose.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base

HEADLINE_MAX_LENGTH = 200
LOCATION_MAX_LENGTH = 120
PHONE_MAX_LENGTH = 40
SKILLS_MAX_LENGTH = 1_000
TEXT_MAX_LENGTH = 5_000


class CandidateProfile(Base):
    """A candidate's profile, one per user."""

    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UNIQUE, not merely indexed: one profile per candidate is the invariant,
    # and the constraint is what enforces it against two concurrent creates.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Basic details
    headline: Mapped[str] = mapped_column(
        String(HEADLINE_MAX_LENGTH), nullable=False, server_default=""
    )
    location: Mapped[str] = mapped_column(
        String(LOCATION_MAX_LENGTH), nullable=False, server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(PHONE_MAX_LENGTH), nullable=False, server_default=""
    )

    # Profile summary
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # Career preferences
    preferred_role: Mapped[str] = mapped_column(
        String(HEADLINE_MAX_LENGTH), nullable=False, server_default=""
    )
    preferred_location: Mapped[str] = mapped_column(
        String(LOCATION_MAX_LENGTH), nullable=False, server_default=""
    )
    preferred_employment_type: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=""
    )

    # Key skills — comma separated, normalised on write. This is what the
    # applicant ranking reads.
    key_skills: Mapped[str] = mapped_column(
        String(SKILLS_MAX_LENGTH), nullable=False, server_default=""
    )

    # Free-text sections
    employment: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    education: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @validates("key_skills")
    def _normalise_skills(self, _key: str, value: str) -> str:
        """Collapse the skill list to a clean, comma-separated form.

        Normalised on the model rather than in a handler so every write path —
        the API, a seed, a future import — stores the same shape. The ranking
        splits on commas, so " React ,, react" becoming "React, react" is the
        difference between two skills and four.
        """
        if not value:
            return ""

        skills = [skill.strip() for skill in value.split(",")]

        return ", ".join(skill for skill in skills if skill)

    def skill_list(self) -> list[str]:
        """The skills as a list, for matching."""
        return [
            skill for skill in (s.strip() for s in self.key_skills.split(",")) if skill
        ]

    def __repr__(self) -> str:
        return f"<CandidateProfile user={self.user_id}>"
