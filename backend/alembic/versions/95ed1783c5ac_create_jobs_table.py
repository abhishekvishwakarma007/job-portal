"""create jobs table

Revision ID: 95ed1783c5ac
Revises: fc12a48cdacf
Create Date: 2026-07-19 20:07:43.536423

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "95ed1783c5ac"
down_revision: str | None = "fc12a48cdacf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Named so downgrade can drop the type explicitly — Postgres keeps an enum
# alive after its last table is dropped, and the next upgrade would then fail
# with "type employment_type already exists".
EMPLOYMENT_TYPE_ENUM = sa.Enum(
    "FULL_TIME",
    "PART_TIME",
    "CONTRACT",
    "INTERNSHIP",
    name="employment_type",
)


def upgrade() -> None:
    """Create the jobs table with its enum, foreign key, and indexes."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=False),
        sa.Column("employment_type", EMPLOYMENT_TYPE_ENUM, nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
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
        # CASCADE so removing an HR account cannot leave postings pointing at a
        # user that no longer exists.
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_created_by_id", "jobs", ["created_by_id"], unique=False)
    # Serves the public browse query — filter on is_published, order by
    # created_at — and, because it leads with is_published, any lookup on that
    # column alone. A separate single-column index would be redundant.
    op.create_index(
        "ix_jobs_published_created_at",
        "jobs",
        ["is_published", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the table, its indexes, and the enum type it would leave behind."""
    op.drop_index("ix_jobs_published_created_at", table_name="jobs")
    op.drop_index("ix_jobs_created_by_id", table_name="jobs")
    op.drop_table("jobs")
    EMPLOYMENT_TYPE_ENUM.drop(op.get_bind())
