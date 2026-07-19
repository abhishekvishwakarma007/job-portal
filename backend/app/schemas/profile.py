"""Request and response shapes for the candidate profile."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import (
    HEADLINE_MAX_LENGTH,
    LOCATION_MAX_LENGTH,
    PHONE_MAX_LENGTH,
    SKILLS_MAX_LENGTH,
    TEXT_MAX_LENGTH,
)


class ProfileUpdate(BaseModel):
    """A profile edit.

    Every field is optional so the UI can save one section at a time without
    resending the rest — and without a partial save blanking the sections the
    user was not editing.
    """

    headline: str | None = Field(default=None, max_length=HEADLINE_MAX_LENGTH)
    location: str | None = Field(default=None, max_length=LOCATION_MAX_LENGTH)
    phone: str | None = Field(default=None, max_length=PHONE_MAX_LENGTH)
    summary: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)
    preferred_role: str | None = Field(default=None, max_length=HEADLINE_MAX_LENGTH)
    preferred_location: str | None = Field(default=None, max_length=LOCATION_MAX_LENGTH)
    preferred_employment_type: str | None = Field(default=None, max_length=40)
    key_skills: str | None = Field(default=None, max_length=SKILLS_MAX_LENGTH)
    employment: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)
    education: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)


class ProfileRead(BaseModel):
    """A profile as returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    headline: str
    location: str
    phone: str
    summary: str
    preferred_role: str
    preferred_location: str
    preferred_employment_type: str
    key_skills: str
    employment: str
    education: str
    created_at: datetime
    updated_at: datetime
