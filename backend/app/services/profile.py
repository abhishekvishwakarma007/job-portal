"""Reading and updating candidate profiles."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import CandidateProfile
from app.models.user import User
from app.schemas.profile import ProfileUpdate


def get_or_create_profile(db: Session, *, user: User) -> CandidateProfile:
    """Return the user's profile, creating an empty one on first access.

    Created on read rather than at registration so an account that never opens
    the profile page carries no empty row, and so profiles exist for accounts
    that predate this feature without a data migration.
    """
    profile = db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    ).scalar_one_or_none()

    if profile is not None:
        return profile

    profile = CandidateProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


def update_profile(
    db: Session, *, profile: CandidateProfile, payload: ProfileUpdate
) -> CandidateProfile:
    """Apply a partial edit.

    exclude_unset is what lets the UI save one section at a time: without it
    every field the caller omitted would arrive as None and blank the rest.
    """
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile
