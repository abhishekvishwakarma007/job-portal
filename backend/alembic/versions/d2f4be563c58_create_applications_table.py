"""create applications table

Revision ID: d2f4be563c58
Revises: 95ed1783c5ac
Create Date: 2026-07-19 20:17:29.695353

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2f4be563c58"
down_revision: str | None = "95ed1783c5ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Named so downgrade can drop the type explicitly — Postgres keeps an enum
# alive after its last table is dropped, and the next upgrade would then fail
# with "type application_status already exists".
APPLICATION_STATUS_ENUM = sa.Enum(
    "SUBMITTED",
    "UNDER_REVIEW",
    "ACCEPTED",
    "REJECTED",
    name="application_status",
)


def upgrade() -> None:
    """Create the applications table with its duplicate-apply constraint."""
    op.create_table(
        "applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=False),
        sa.Column(
            "status",
            APPLICATION_STATUS_ENUM,
            server_default="SUBMITTED",
            nullable=False,
        ),
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
        # CASCADE on both sides: an application is meaningless once either the
        # job or the candidate is gone, and a dangling row breaks every join.
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # The duplicate-apply backstop. A service-layer check loses the race
        # between two concurrent submissions; this cannot.
        sa.UniqueConstraint(
            "job_id", "candidate_id", name="uq_applications_job_candidate"
        ),
    )
    op.create_index(
        "ix_applications_candidate_id", "applications", ["candidate_id"], unique=False
    )
    # Serves the HR pipeline query — filter on job_id, order by created_at —
    # and, because it leads with job_id, any lookup on that column alone. A
    # separate single-column index would be redundant.
    op.create_index(
        "ix_applications_job_created_at",
        "applications",
        ["job_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the table, its indexes, and the enum type it would leave behind."""
    op.drop_index("ix_applications_job_created_at", table_name="applications")
    op.drop_index("ix_applications_candidate_id", table_name="applications")
    op.drop_table("applications")
    APPLICATION_STATUS_ENUM.drop(op.get_bind())
