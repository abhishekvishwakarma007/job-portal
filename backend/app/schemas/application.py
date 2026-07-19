"""Request and response shapes for applications.

The create schema carries no status and no candidate_id: both are
server-assigned. A candidate who adds `"status": "ACCEPTED"` to their body gets
it ignored rather than honoured.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import COVER_LETTER_MAX_LENGTH, ApplicationStatus
from app.schemas.auth import UserRead
from app.schemas.job import JobRead


class ApplicationCreate(BaseModel):
    """A candidate's submission to one job."""

    job_id: uuid.UUID
    cover_letter: str = Field(min_length=1, max_length=COVER_LETTER_MAX_LENGTH)


class ApplicationStatusUpdate(BaseModel):
    """An HR decision moving the application through the pipeline."""

    status: ApplicationStatus


class ApplicationRead(BaseModel):
    """An application as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job: JobRead
    candidate: UserRead
    cover_letter: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    """One page of applications."""

    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int
