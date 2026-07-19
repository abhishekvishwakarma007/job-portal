"""add login lockout columns

Revision ID: 6546c35c6a51
Revises: d2f4be563c58
Create Date: 2026-07-19 21:12:29.778659

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6546c35c6a51"
down_revision: str | None = "d2f4be563c58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add per-account lockout state.

    Kept in the database rather than in process memory so it survives a restart
    and holds across every worker — an in-memory counter resets exactly when a
    sustained attack is still running.

    The server_default matters for the existing rows: without it, adding a
    NOT NULL column to a populated table fails.
    """
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    # Nullable: null means "never locked", which is the correct starting state
    # and distinguishable from a lock that has since expired.
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop the lockout columns."""
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
