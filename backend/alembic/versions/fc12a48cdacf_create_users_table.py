"""create users table

Revision ID: fc12a48cdacf
Revises:
Create Date: 2026-07-19 18:52:19.018107

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fc12a48cdacf"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Named so downgrade can drop the type explicitly. Postgres keeps an enum type
# alive after its last table is dropped, so without this a downgrade followed
# by an upgrade fails with "type user_role already exists".
USER_ROLE_ENUM = sa.Enum("HR", "CANDIDATE", name="user_role")


def upgrade() -> None:
    """Create the users table, its role enum, and the email uniqueness index."""
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("role", USER_ROLE_ENUM, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Built on lower(email) so the uniqueness guarantee survives any write path
    # that bypasses the ORM's normaliser.
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    """Drop the table, its index, and the enum type it left behind."""
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_table("users")
    USER_ROLE_ENUM.drop(op.get_bind())
