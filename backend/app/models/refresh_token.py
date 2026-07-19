"""Refresh token model.

Only a hash of each token is stored, never the token itself. A database dump
then yields nothing usable, exactly as it does for passwords — the difference
being the hash here is a plain SHA-256 rather than bcrypt, because these values
are 256 bits of `secrets` output rather than something a person chose. There is
no dictionary to attack, so a slow hash would only cost latency on every
refresh.

`replaced_by_id` makes each rotation a link in a chain, which is what turns
"this token was already used" into a detectable theft rather than a puzzle.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# SHA-256 as hex.
TOKEN_HASH_LENGTH = 64


class RefreshToken(Base):
    """One issued refresh token, live or spent."""

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        # Revoking a user's whole family on a reuse detection touches every row
        # they own, and expiring old rows scans by user too.
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Unique so a presented token resolves to exactly one row — the lookup is
    # an equality match on this column, so it must also be indexed, which
    # UNIQUE provides.
    token_hash: Mapped[str] = mapped_column(
        String(TOKEN_HASH_LENGTH),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # Null while the token is live. Set on rotation, on logout, and on every
    # token in the family when one is replayed.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # The token issued in this one's place. SET NULL rather than CASCADE: losing
    # the successor should not delete the audit trail of what it replaced.
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """Deliberately omits the hash so it cannot reach a log line."""
        return (
            f"<RefreshToken id={self.id} user={self.user_id} "
            f"revoked={self.revoked_at is not None}>"
        )
