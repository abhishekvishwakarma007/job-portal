"""User model and role enum.

Two roles, no admin tier: HR posts and manages jobs, CANDIDATE browses and
applies. Authorisation everywhere derives from this single field.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base

# Bcrypt emits 60-char hashes, but the column is sized for future algorithm
# changes (argon2 hashes are longer) so a migration is not forced later.
PASSWORD_HASH_LENGTH = 255

# RFC 5321 caps the full path at 254 characters.
EMAIL_MAX_LENGTH = 254
FULL_NAME_MAX_LENGTH = 120


class UserRole(StrEnum):
    """Role determining what a user may do.

    StrEnum so the value serialises directly to JSON and compares equal to its
    string form, which keeps API schemas and DB values in one vocabulary.
    """

    HR = "HR"
    CANDIDATE = "CANDIDATE"


class User(Base):
    """An authenticated account, either an HR user or a candidate.

    Emails are stored lower-cased and carry a case-insensitive UNIQUE index, so
    "Admin@test.com" cannot register alongside "admin@test.com" — that would
    otherwise split one identity across two accounts and defeat the
    duplicate-application guard.

    Look accounts up with `func.lower(User.email) == value.lower()`: that is the
    expression the unique index is built on, so it is the form Postgres can
    serve from the index.
    """

    __tablename__ = "users"

    __table_args__ = (
        # Built on lower(email) rather than email, because the normaliser below
        # is application-level and every non-ORM path bypasses it — a seed
        # script, an admin's psql session, a bulk import. A plain UNIQUE(email)
        # would accept "HR@Demo.com" next to "hr@demo.com" and hand one person
        # two accounts for the same inbox. This is the constraint that actually
        # holds the invariant; the validator is only the friendly first line.
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Uniqueness lives in the case-insensitive index in __table_args__, not on
    # this column: it is the backstop that makes concurrent duplicate
    # registrations impossible rather than merely unlikely.
    email: Mapped[str] = mapped_column(
        String(EMAIL_MAX_LENGTH),
        nullable=False,
    )
    # Named hashed_password, never `password`, so a plaintext value has no
    # column to land in even by mistake.
    hashed_password: Mapped[str] = mapped_column(
        String(PASSWORD_HASH_LENGTH),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(FULL_NAME_MAX_LENGTH),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True, validate_strings=True),
        nullable=False,
    )
    # Checked on every request rather than only at login, so disabling an
    # account locks it out immediately instead of when its token expires.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    # Lockout state lives in the database rather than in process memory, so it
    # survives a restart and holds across every worker — an in-memory counter
    # would reset the moment the container it lived in was replaced, which is
    # exactly when a sustained attack is still running.
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    # Null means not locked. A timestamp in the past is equivalent, and is left
    # rather than cleared so the column also records that a lockout happened.
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        """Lower-case and trim the email before it reaches the DB.

        Enforced on the model rather than in a service function so that every
        ORM path — registration, seeding, tests — stores one canonical form and
        gets a clean error instead of an index violation. Anything that skips
        the ORM still hits the case-insensitive unique index above.
        """
        return value.strip().lower()

    def __repr__(self) -> str:
        """Deliberately omits the password hash so it cannot reach a log."""
        return f"<User id={self.id} email={self.email} role={self.role}>"
