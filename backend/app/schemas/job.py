"""Request and response shapes for job postings.

The create schema has no created_by_id: ownership is taken from the
authenticated caller, never from the body, so one HR user cannot post a role in
another's name by adding a field to their request.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import (
    COMPANY_MAX_LENGTH,
    LOCATION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    EmploymentType,
)
from app.schemas.auth import UserRead

DESCRIPTION_MAX_LENGTH = 20_000

# An unbounded list is a denial-of-service primitive: one request asking for
# every row will happily exhaust memory once the table is large.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class JobCreate(BaseModel):
    """A new posting. Ownership and timestamps are server-assigned."""

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    company: str = Field(min_length=1, max_length=COMPANY_MAX_LENGTH)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    location: str = Field(min_length=1, max_length=LOCATION_MAX_LENGTH)
    employment_type: EmploymentType
    is_published: bool = True


class JobUpdate(BaseModel):
    """A partial edit.

    Every field is optional and `None` means "not supplied" rather than "set to
    null", so a PATCH naming one field cannot blank the rest.
    """

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    company: str | None = Field(default=None, min_length=1, max_length=COMPANY_MAX_LENGTH)
    description: str | None = Field(
        default=None, min_length=1, max_length=DESCRIPTION_MAX_LENGTH
    )
    location: str | None = Field(
        default=None, min_length=1, max_length=LOCATION_MAX_LENGTH
    )
    employment_type: EmploymentType | None = None
    is_published: bool | None = None


class JobRead(BaseModel):
    """A posting as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    description: str
    location: str
    employment_type: EmploymentType
    is_published: bool
    created_by: UserRead
    created_at: datetime
    updated_at: datetime


class JobPage(BaseModel):
    """One page of postings.

    Carries the total so the UI can render pagination without a second call.
    """

    items: list[JobRead]
    total: int
    limit: int
    offset: int
