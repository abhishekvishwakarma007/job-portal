"""Authentication routes: registration, login, and the current user.

Handlers stay thin — they translate service-layer outcomes into status codes.
The rules themselves live in app.services.auth so they can be exercised, and
reused, without going through HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.rate_limit import (
    SlidingWindowRateLimiter,
    login_rate_limiter,
    register_rate_limiter,
)
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    Token,
    UserCreate,
    UserRead,
)
from app.services.auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)
from app.services.refresh_token import (
    InvalidRefreshTokenError,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for every login failure. Distinguishing "no such account" from
# "wrong password" would turn this endpoint into a membership oracle: an
# attacker could confirm which addresses hold accounts without ever guessing a
# password correctly.
_INVALID_CREDENTIALS_DETAIL = "Incorrect email or password"


def _client_key(request: Request) -> str:
    """Identify the caller for rate-limiting purposes.

    The direct peer address, deliberately: X-Forwarded-For is attacker-supplied
    unless a trusted proxy overwrites it, so honouring it here would let anyone
    reset their own budget by inventing a header. A deployment behind a real
    load balancer should read the header the balancer sets and is documented as
    a limitation.
    """
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(limiter: SlidingWindowRateLimiter, request: Request) -> str:
    """Consume one unit of the caller's budget, or raise 429."""
    key = _client_key(request)
    result = limiter.check(key)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            # Retry-After is what lets a well-behaved client back off correctly
            # instead of hammering and staying blocked.
            headers={"Retry-After": str(result.retry_after)},
        )

    return key


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def register(
    payload: UserCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Register a new HR or candidate account.

    Returns 409 when the address is taken. Registration necessarily reveals
    whether an address exists — there is no way to confirm a new account
    without it — which is why login is careful not to, and why this endpoint
    is rate limited: the 409 is an enumeration oracle if it can be called
    without limit.
    """
    _enforce_rate_limit(register_rate_limiter, request)

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
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Issue an access token for valid credentials.

    Two independent controls, because they stop different attacks. The rate
    limit is per caller and blunts spraying one password across many accounts;
    the lockout is per account and blunts guessing many passwords against one.
    Neither substitutes for the other.
    """
    key = _enforce_rate_limit(login_rate_limiter, request)

    try:
        user = authenticate_user(db, email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # A caller who proved they own an account should not spend the rest of the
    # window locked out of their own sign-ins by earlier typos.
    login_rate_limiter.reset(key)

    return Token(
        access_token=create_access_token(user_id=user.id, role=user.role),
        refresh_token=issue_refresh_token(db, user=user),
    )


@router.post("/refresh", response_model=Token, summary="Exchange a refresh token")
def refresh(
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Spend a refresh token and return a fresh pair.

    Not rate limited by caller address: a client with a valid token has already
    proved possession, and the presented token being single-use is a far
    tighter budget than any per-IP counter. Replaying a spent one revokes the
    whole family rather than merely failing.
    """
    try:
        user, new_refresh_token = rotate_refresh_token(
            db, raw_token=payload.refresh_token
        )
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return Token(
        access_token=create_access_token(user_id=user.id, role=user.role),
        refresh_token=new_refresh_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End the session",
)
def logout(
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Revoke the presented refresh token.

    Always 204, even for a token that was never issued or is already spent.
    Logging out should succeed regardless, and a different answer would confirm
    which tokens were real to anyone able to call this.

    The access token is not revoked — it is stateless and expires on its own
    within minutes. Revoking it would mean checking a blocklist on every
    request, which is the cost this design exists to avoid.
    """
    revoke_refresh_token(db, raw_token=payload.refresh_token)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead, summary="The authenticated user")
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the caller's own account, re-read from the database."""
    return UserRead.model_validate(current_user)
