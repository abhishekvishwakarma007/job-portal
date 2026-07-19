"""add company to jobs

Revision ID: 57966f47f694
Revises: 73e7d1f0d02b

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "57966f47f694"
down_revision: str | None = "73e7d1f0d02b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the hiring company to each posting.

    The server_default is what lets this run against a populated table: a
    NOT NULL column with no default cannot be added to existing rows.
    "Confidential" is a real answer on a job board, not a placeholder, so
    pre-existing rows read sensibly rather than showing a filler string.
    """
    op.add_column(
        "jobs",
        sa.Column(
            "company",
            sa.String(length=120),
            server_default="Confidential",
            nullable=False,
        ),
    )
    # Indexed because company is one of the browse filters, and an unindexed
    # ILIKE over it scans every posting.
    op.create_index("ix_jobs_company", "jobs", ["company"], unique=False)


def downgrade() -> None:
    """Drop the company column."""
    op.drop_index("ix_jobs_company", table_name="jobs")
    op.drop_column("jobs", "company")
