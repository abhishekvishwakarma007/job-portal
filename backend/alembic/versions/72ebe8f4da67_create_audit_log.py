"""create audit log

Revision ID: 72ebe8f4da67
Revises: 5439ba5c442b

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "72ebe8f4da67"
down_revision: str | None = "5439ba5c442b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the append-only audit log.

    entity_id carries no foreign key deliberately: an entry has to outlive the
    record it describes, and a FK to a deleted job would either block the
    delete or cascade the evidence away with it.
    """
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_email", sa.String(length=254), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # SET NULL: deleting an account must not erase what it did. The entry
        # keeps actor_email, so it still names who acted.
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # The two questions actually asked of a log: what happened to this record,
    # and what did this person do.
    op.create_index(
        "ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(
        "ix_audit_log_actor_created",
        "audit_log",
        ["actor_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the audit log."""
    op.drop_index("ix_audit_log_actor_created", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_table("audit_log")
