"""ORM models.

Every model is re-exported here so that importing `app.models` populates
Base.metadata with the full schema — Alembic's autogenerate relies on that.
"""

from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditAction, AuditLogEntry
from app.models.job import EmploymentType, Job
from app.models.notification import Notification
from app.models.profile import CandidateProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole

__all__ = [
    "Application",
    "ApplicationStatus",
    "AuditAction",
    "AuditLogEntry",
    "CandidateProfile",
    "EmploymentType",
    "Job",
    "Notification",
    "RefreshToken",
    "User",
    "UserRole",
]
