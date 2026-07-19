"""ORM models.

Every model is re-exported here so that importing `app.models` populates
Base.metadata with the full schema — Alembic's autogenerate relies on that.
"""

from app.models.user import User, UserRole

__all__ = ["User", "UserRole"]
