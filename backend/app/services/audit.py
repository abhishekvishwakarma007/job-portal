"""Recording sensitive state changes.

One function, called from the service layer rather than the routes, so an
action is logged wherever it is triggered from — the API today, a CLI or
background job later. A log that only records what the HTTP layer happened to
do is a log with holes in it.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditLogEntry
from app.models.user import User


def record(
    db: Session,
    *,
    actor: User,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID,
    summary: str = "",
) -> AuditLogEntry:
    """Append an entry.

    The caller commits. Sharing the caller's transaction is the point: if the
    change rolls back, so does its log entry, and the log never claims
    something happened that did not.

    actor_email is copied rather than joined, so the entry still names who did
    it after that account is deleted.
    """
    entry = AuditLogEntry(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
    )
    db.add(entry)

    return entry


def entries_for(
    db: Session, *, entity_type: str, entity_id: uuid.UUID
) -> list[AuditLogEntry]:
    """Everything recorded against one record, oldest first.

    Ascending because a history reads forwards — this is the sequence of what
    happened, not a feed of what is newest.
    """
    return list(
        db.execute(
            select(AuditLogEntry)
            .where(
                AuditLogEntry.entity_type == entity_type,
                AuditLogEntry.entity_id == entity_id,
            )
            .order_by(AuditLogEntry.created_at)
        )
        .scalars()
        .all()
    )
