"""Request and response shapes for notifications and recommendations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application import ApplicationRead

MESSAGE_MAX_LENGTH = 2_000


class NotificationRead(BaseModel):
    """A notification as returned to its recipient."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    body: str
    is_read: bool
    job_id: uuid.UUID | None
    created_at: datetime


class NotificationPage(BaseModel):
    """One page of notifications, with the unread count for the header badge."""

    items: list[NotificationRead]
    total: int
    unread: int
    limit: int
    offset: int


class ContactApplicantRequest(BaseModel):
    """An HR user's message to an applicant.

    Subject and recipient are server-assigned: the subject is derived from the
    posting, and the recipient from the application, so a message cannot be
    addressed to someone who never applied.
    """

    message: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)


class RecommendedApplicant(BaseModel):
    """One applicant with the keyword score that ranked them."""

    application: ApplicationRead
    # 0-1, the share of the posting's vocabulary the cover letter covers.
    score: float
    matched_terms: list[str]


class RecommendationPage(BaseModel):
    """Ranked applicants for a posting.

    `method` is stated in the payload rather than left implicit so no client
    presents this as more than it is — a keyword overlap, not an assessment of
    whether someone can do the job.
    """

    items: list[RecommendedApplicant]
    method: str = "keyword-overlap"
