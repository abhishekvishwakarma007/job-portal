"""create refresh tokens table

Revision ID: 73e7d1f0d02b
Revises: 6546c35c6a51
Create Date: 2026-07-19 21:27:25.650818

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "73e7d1f0d02b"
down_revision: str | None = "6546c35c6a51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the refresh token store.

    Only hashes are held, so a database dump yields nothing usable — the same
    property passwords have, achieved with a plain SHA-256 because these values
    are 256 bits of `secrets` output rather than something a person chose.
    """
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # SET NULL, not CASCADE: losing a successor token must not delete the
        # audit trail of what it replaced.
        sa.ForeignKeyConstraint(
            ["replaced_by_id"], ["refresh_tokens.id"], ondelete="SET NULL"
        ),
        # CASCADE: tokens for a deleted account are unusable by definition.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Also provides the index the presented-token lookup needs.
        sa.UniqueConstraint("token_hash"),
    )
    # Revoking a whole family on a replay touches every row a user owns.
    op.create_index(
        "ix_refresh_tokens_user_revoked",
        "refresh_tokens",
        ["user_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the refresh token store."""
    op.drop_index("ix_refresh_tokens_user_revoked", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
