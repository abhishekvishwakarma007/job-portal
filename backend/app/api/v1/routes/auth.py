"""Authentication routes: registration, login, and the current user.

Handlers stay thin — they translate service-layer outcomes into status codes.
The rules themselves live in app.services.auth so they can be exercised, and
reused, without going through HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, Token, UserCreate, UserRead
from app.services.auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for every login failure. Distinguishing "no such account" from
# "wrong password" would turn this endpoint into a membership oracle: an
# attacker could confirm which addresses hold accounts without ever guessing a
# password correctly.
_INVALID_CREDENTIALS_DETAIL = "Incorrect email or password"


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def register(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Register a new HR or candidate account.

    Returns 409 when the address is taken. Registration necessarily reveals
    whether an address exists — there is no way to confirm a new account
    without it — which is why login is careful not to.
    """
    try:
        user = register_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange credentials for a token",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Issue an access token for valid credentials."""
    try:
        user = authenticate_user(db, email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return Token(access_token=create_access_token(user_id=user.id, role=user.role))


@router.get("/me", response_model=UserRead, summary="The authenticated user")
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the caller's own account, re-read from the database."""
    return UserRead.model_validate(current_user)
