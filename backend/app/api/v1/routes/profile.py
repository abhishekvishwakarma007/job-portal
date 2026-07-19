"""Candidate profile routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CandidateUser
from app.db.session import get_db
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.services.profile import get_or_create_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=ProfileRead, summary="Your profile")
def read_my_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: CandidateUser,
) -> ProfileRead:
    """Return the caller's profile, creating an empty one on first access."""
    return ProfileRead.model_validate(get_or_create_profile(db, user=current_user))


@router.patch("/me", response_model=ProfileRead, summary="Update your profile")
def update_my_profile(
    payload: ProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: CandidateUser,
) -> ProfileRead:
    """Apply a partial edit to the caller's own profile.

    Candidate-only, and scoped to the caller: there is no path here to read or
    write anyone else's profile, so ownership needs no separate check.
    """
    profile = get_or_create_profile(db, user=current_user)

    return ProfileRead.model_validate(
        update_profile(db, profile=profile, payload=payload)
    )
