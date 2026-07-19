"""Refresh token rotation, revocation, and replay detection.

The replay tests are the reason this mechanism exists. Rotation alone narrows
the window a stolen token is useful for; detecting the replay is what turns the
theft into something the system notices and acts on.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services.auth import register_user
from app.services.refresh_token import (
    InvalidRefreshTokenError,
    issue_refresh_token,
    revoke_family,
    revoke_refresh_token,
    rotate_refresh_token,
)

PASSWORD = "Str0ng@Password"


@pytest.fixture
def user(db_session: Session) -> User:
    """An account holding refresh tokens."""
    return register_user(
        db_session,
        email="candidate@test.com",
        password=PASSWORD,
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    )


def stored_tokens(db: Session) -> list[RefreshToken]:
    """Every token row, oldest first."""
    return list(
        db.execute(select(RefreshToken).order_by(RefreshToken.created_at)).scalars().all()
    )


def test_issued_token_is_not_stored_in_the_clear(
    db_session: Session, user: User, valid_env: None
) -> None:
    """A database dump must not yield usable tokens."""
    raw = issue_refresh_token(db_session, user=user)

    rows = stored_tokens(db_session)
    assert len(rows) == 1
    assert rows[0].token_hash != raw
    assert raw not in rows[0].token_hash


def test_each_issued_token_is_unique(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Two sign-ins must not produce the same credential."""
    assert issue_refresh_token(db_session, user=user) != issue_refresh_token(
        db_session, user=user
    )


def test_rotation_returns_the_owner_and_a_new_token(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Happy path."""
    raw = issue_refresh_token(db_session, user=user)

    rotated_user, new_raw = rotate_refresh_token(db_session, raw_token=raw)

    assert rotated_user.id == user.id
    assert new_raw != raw


def test_rotation_spends_the_presented_token(
    db_session: Session, user: User, valid_env: None
) -> None:
    """The old token must stop working immediately."""
    raw = issue_refresh_token(db_session, user=user)
    rotate_refresh_token(db_session, raw_token=raw)

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=raw)


def test_rotation_links_the_replacement(
    db_session: Session, user: User, valid_env: None
) -> None:
    """The chain is what makes a replay attributable rather than mysterious."""
    raw = issue_refresh_token(db_session, user=user)
    rotate_refresh_token(db_session, raw_token=raw)

    rows = stored_tokens(db_session)
    original, replacement = rows[0], rows[1]
    assert original.revoked_at is not None
    assert original.replaced_by_id == replacement.id


def test_the_new_token_works(db_session: Session, user: User, valid_env: None) -> None:
    """Rotation must not strand the legitimate client."""
    raw = issue_refresh_token(db_session, user=user)
    _, second = rotate_refresh_token(db_session, raw_token=raw)

    third_user, _ = rotate_refresh_token(db_session, raw_token=second)

    assert third_user.id == user.id


def test_replaying_a_spent_token_revokes_the_whole_family(
    db_session: Session, user: User, valid_env: None
) -> None:
    """The decisive property.

    A legitimate client never replays a spent token, so a replay is evidence
    that two parties hold tokens from one chain. There is no way to tell the
    attacker's copy from the victim's, so both are invalidated and everyone
    signs in again.
    """
    raw = issue_refresh_token(db_session, user=user)
    _, live = rotate_refresh_token(db_session, raw_token=raw)

    # The attacker replays the token the victim already spent.
    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=raw)

    # The victim's current token is now dead too — deliberately.
    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=live)


def test_unknown_token_is_rejected(
    db_session: Session, user: User, valid_env: None
) -> None:
    """A value that was never issued must not authenticate."""
    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token="never-issued")


def test_expired_token_is_rejected(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Expiry is enforced, not merely recorded."""
    raw = issue_refresh_token(db_session, user=user)
    stored_tokens(db_session)[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=raw)


def test_token_for_a_deactivated_user_is_rejected(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Deactivation must not be survivable by refreshing.

    Otherwise a disabled account could mint fresh access tokens indefinitely,
    which defeats disabling it.
    """
    raw = issue_refresh_token(db_session, user=user)
    user.is_active = False
    db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=raw)


def test_revoking_a_token_stops_it_working(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Logout must actually end the session."""
    raw = issue_refresh_token(db_session, user=user)

    revoke_refresh_token(db_session, raw_token=raw)

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db_session, raw_token=raw)


def test_revoking_an_unknown_token_is_silent(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Logout should succeed regardless, and not confirm what was ever real."""
    revoke_refresh_token(db_session, raw_token="never-issued")


def test_revoking_one_token_leaves_other_sessions_alone(
    db_session: Session, user: User, valid_env: None
) -> None:
    """Signing out of one device must not sign out the others."""
    phone = issue_refresh_token(db_session, user=user)
    laptop = issue_refresh_token(db_session, user=user)

    revoke_refresh_token(db_session, raw_token=phone)

    rotated_user, _ = rotate_refresh_token(db_session, raw_token=laptop)
    assert rotated_user.id == user.id


def test_revoke_family_ends_every_session(
    db_session: Session, user: User, valid_env: None
) -> None:
    """The "sign out everywhere" primitive."""
    phone = issue_refresh_token(db_session, user=user)
    laptop = issue_refresh_token(db_session, user=user)

    revoke_family(db_session, user_id=user.id)

    for token in (phone, laptop):
        with pytest.raises(InvalidRefreshTokenError):
            rotate_refresh_token(db_session, raw_token=token)


def test_revoke_family_leaves_other_users_alone(
    db_session: Session, user: User, valid_env: None
) -> None:
    """One user's replay must not sign out everybody else."""
    other = register_user(
        db_session,
        email="hr@test.com",
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )
    other_token = issue_refresh_token(db_session, user=other)
    issue_refresh_token(db_session, user=user)

    revoke_family(db_session, user_id=user.id)

    rotated_user, _ = rotate_refresh_token(db_session, raw_token=other_token)
    assert rotated_user.id == other.id
