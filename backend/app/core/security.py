"""Password hashing and access-token signing.

Every authorisation decision in the application rests on these two primitives,
so both fail closed: a hash that cannot be parsed is a failed login rather than
a 500, and a token that cannot be verified for any reason raises the same error
as one that was never supplied.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.models.user import UserRole

ALGORITHM = "HS256"

# bcrypt hashes at most 72 bytes and silently ignores the rest, which would make
# "<72 bytes>abc" and "<72 bytes>xyz" the same credential. Refuse instead.
MAX_PASSWORD_BYTES = 72


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, badly signed, or nonsensical.

    One exception for every failure mode on purpose: the caller must not be able
    to tell an expired token from a forged one, and neither must the client.
    """


@dataclass(frozen=True)
class TokenPayload:
    """The claims we are willing to trust after verifying a signature."""

    user_id: uuid.UUID
    role: UserRole


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of the password.

    The salt is generated per call and stored inside the hash, so two accounts
    with the same password produce different hashes and one cracked password
    does not reveal the others.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes; "
            f"got {len(encoded)}."
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True when the password matches the stored hash.

    Returns False rather than raising on a malformed hash: a row damaged by a
    bad migration should fail that one login, not 500 every attempt against it.
    """
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Return a signed JWT identifying the user and their role.

    The role is embedded so routine authorisation needs no database read, but it
    is never the authority on its own — callers re-read the user (see
    `get_current_user`) so a revoked role cannot outlive its token.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    claims = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(claims, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Verify a token's signature and expiry and return its claims.

    Pinning `algorithms` is what prevents an attacker re-signing the payload with
    "alg": "none", or with HMAC against a public key, and having it accepted.
    """
    settings = get_settings()

    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token could not be verified") from exc

    try:
        user_id = uuid.UUID(claims["sub"])
        role = UserRole(claims["role"])
    except (KeyError, ValueError) as exc:
        # A correctly-signed token can still be unusable — an unrecognised role
        # would otherwise reach the authorisation layer as an undefined state.
        raise InvalidTokenError("Token claims are not usable") from exc

    return TokenPayload(user_id=user_id, role=role)
