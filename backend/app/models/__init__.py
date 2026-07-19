"""ORM models.

Every model is re-exported here so that importing `app.models` populates
Base.metadata with the full schema — Alembic's autogenerate relies on that.
"""

from app.models.application import Application, ApplicationStatus
from app.models.job import EmploymentType, Job
from app.models.user import User, UserRole

__all__ = [
    "Application",
    "ApplicationStatus",
    "EmploymentType",
    "Job",
    "User",
    "UserRole",
]
