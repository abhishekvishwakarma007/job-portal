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
from app.models.user import User

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
