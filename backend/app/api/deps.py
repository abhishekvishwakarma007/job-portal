"""Shared route dependencies.

`get_current_user` is the single place a request turns into an identity, so
every endpoint inherits the same rules about expiry, deactivation, and what a
token is allowed to assert.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

# auto_error=False so a missing header reaches our own handler: Starlette's
# default for absent credentials is 403, and "you are not authenticated" is a
# 401. Every rejection below is deliberately identical to the others.
_bearer_scheme = HTTPBearer(auto_error=False, description="Bearer access token")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the bearer token to a live, active user.

    The user is re-read from the database on every request rather than trusted
    from the token's claims. That is what makes deactivation and role changes
    take effect immediately instead of whenever the token happens to expire —
    a dismissed employee otherwise keeps their access for the rest of its life.
    """
    if credentials is None:
        raise _UNAUTHENTICATED

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _UNAUTHENTICATED from exc

    # A SELECT rather than Session.get: get() can answer from the identity map
    # without touching the database, which would defeat the point of re-reading.
    user = db.execute(select(User).where(User.id == payload.user_id)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise _UNAUTHENTICATED

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Resolve the caller if they supplied a usable token, else None.

    For endpoints that are public but behave differently when signed in — job
    browsing shows an HR user their own drafts. A bad token is treated as
    anonymous rather than rejected, so a stale token in a browser degrades to
    the public view instead of breaking the page.
    """
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        return None

    user = db.execute(select(User).where(User.id == payload.user_id)).scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_hr(current_user: CurrentUser) -> User:
    """Admit only HR users.

    403 rather than 404 here because the endpoint itself is the restricted
    thing, and its existence is public knowledge from the OpenAPI schema.
    Hiding a *record* is different — that is where 404-over-403 applies, and
    the job service handles it.
    """
    if current_user.role is not UserRole.HR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an HR account",
        )

    return current_user


HRUser = Annotated[User, Depends(require_hr)]
