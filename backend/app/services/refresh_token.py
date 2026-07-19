"""Refresh token issuing, rotation, and revocation.

Rotation-on-use is the point. Each refresh spends the presented token and
returns a new one, so a stolen token is useful only until the legitimate client
next refreshes — and the moment a spent token is presented again, that is proof
something went wrong, because a well-behaved client never replays one.

What follows from that proof is the important part: a replay revokes the user's
entire family, not just the offending token. The attacker and the victim both
hold tokens from the same chain and there is no way to tell which is which, so
the safe answer is to invalidate both and make everyone sign in again.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User

# 32 bytes of urandom, url-safe encoded. Well past guessing range, which is why
# a fast hash is sufficient to store it.
TOKEN_BYTES = 32


class InvalidRefreshTokenError(Exception):
    """Raised when a token is unknown, expired, revoked, or its user is gone.

    One exception for every case on purpose: the caller must not be able to
    tell "never existed" from "already spent", or a probe becomes an oracle
    for which tokens were ever real.
    """


def _hash_token(raw_token: str) -> str:
    """Return the stored form of a token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, *, user: User) -> str:
    """Create a token for the user and return its raw value.

    The raw value is returned once and never stored, so this is the only moment
    it exists outside the client.
    """
    settings = get_settings()
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)

    db.add(
        RefreshToken(
            token_hash=_hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.commit()

    return raw_token


def revoke_family(db: Session, *, user_id: uuid.UUID) -> None:
    """Revoke every live token belonging to a user.

    Used on a replay, and available for a "sign out everywhere" action.
    """
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    db.commit()


def _load_token(db: Session, raw_token: str) -> RefreshToken | None:
    """Find the stored row for a presented token."""
    return db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw_token))
    ).scalar_one_or_none()


def rotate_refresh_token(db: Session, *, raw_token: str) -> tuple[User, str]:
    """Spend a token and issue its replacement.

    Returns the owning user and the new raw token. Raises
    InvalidRefreshTokenError for anything that is not a live, unexpired token
    belonging to an active account.
    """
    stored = _load_token(db, raw_token)

    if stored is None:
        raise InvalidRefreshTokenError

    # A token that was already spent is being replayed. A legitimate client
    # never does this, so treat it as theft and burn the whole chain — the
    # attacker's copy and the victim's are indistinguishable from here.
    if stored.revoked_at is not None:
        revoke_family(db, user_id=stored.user_id)
        raise InvalidRefreshTokenError

    if stored.expires_at <= datetime.now(UTC):
        raise InvalidRefreshTokenError

    user = db.get(User, stored.user_id)

    # Re-read rather than trusting the token's mere existence: an account
    # deactivated since the token was issued must not be able to refresh its
    # way into a new access token.
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError

    settings = get_settings()
    new_raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    replacement = RefreshToken(
        token_hash=_hash_token(new_raw_token),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(replacement)
    db.flush()  # assigns replacement.id for the link below

    stored.revoked_at = datetime.now(UTC)
    stored.replaced_by_id = replacement.id

    db.commit()

    return user, new_raw_token


def revoke_refresh_token(db: Session, *, raw_token: str) -> None:
    """Revoke a single token, as on logout.

    Silent when the token is unknown or already spent: logout should succeed
    regardless, and reporting otherwise would confirm whether a token was ever
    real to anyone who could call it.
    """
    stored = _load_token(db, raw_token)

    if stored is None or stored.revoked_at is not None:
        return

    stored.revoked_at = datetime.now(UTC)
    db.commit()
