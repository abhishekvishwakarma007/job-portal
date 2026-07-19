"""Account lockout.

The per-account control: it blunts guessing many passwords against one account.
The per-caller rate limit in test_auth_rate_limit.py is a separate control
against a different attack, and neither substitutes for the other.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models.user import User, UserRole
from app.services.auth import (
    MAX_FAILED_LOGIN_ATTEMPTS,
    InvalidCredentialsError,
    authenticate_user,
    is_locked,
    register_user,
)

LOGIN_URL = f"{API_V1_PREFIX}/auth/login"

EMAIL = "hr@test.com"
PASSWORD = "Str0ng@Password"
WRONG_PASSWORD = "Wr0ng@Password"


@pytest.fixture
def client(valid_env: None, db_session: Session) -> Iterator[TestClient]:
    """A TestClient sharing the test's session."""
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    """An HR account to attack."""
    return register_user(
        db_session,
        email=EMAIL,
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )


def fail_login(db: Session, times: int) -> None:
    """Submit `times` wrong passwords through the service layer."""
    for _ in range(times):
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(db, email=EMAIL, password=WRONG_PASSWORD)


# --------------------------------------------------------------------------
# Lockout
# --------------------------------------------------------------------------


def test_a_new_account_is_not_locked(db_session: Session, user: User) -> None:
    """Baseline."""
    assert is_locked(user) is False
    assert user.failed_login_attempts == 0


def test_failed_attempts_are_counted(db_session: Session, user: User) -> None:
    """Each wrong password increments the counter."""
    fail_login(db_session, 3)

    db_session.refresh(user)
    assert user.failed_login_attempts == 3
    assert is_locked(user) is False


def test_account_locks_at_the_threshold(db_session: Session, user: User) -> None:
    """The lockout engages once the budget is spent."""
    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS)

    db_session.refresh(user)
    assert is_locked(user) is True
    assert user.locked_until is not None


def test_correct_password_is_refused_while_locked(
    db_session: Session, user: User
) -> None:
    """The decisive property.

    Checking the password before the lock would let an attacker keep probing
    and learn they had guessed right the moment it unlocked — the lockout would
    slow them without ever stopping the confirmation.
    """
    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, email=EMAIL, password=PASSWORD)


def test_login_succeeds_once_the_lock_expires(db_session: Session, user: User) -> None:
    """A lockout is temporary — an account must never be permanently bricked."""
    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS)

    db_session.refresh(user)
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    assert authenticate_user(db_session, email=EMAIL, password=PASSWORD).id == user.id


def test_successful_login_clears_the_counter(db_session: Session, user: User) -> None:
    """Otherwise yesterday's typos would accumulate toward tomorrow's lockout."""
    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS - 1)

    authenticate_user(db_session, email=EMAIL, password=PASSWORD)

    db_session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_backoff_grows_with_repeated_lockouts(db_session: Session, user: User) -> None:
    """Each failure past the threshold costs an attacker more than the last."""
    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS)
    db_session.refresh(user)
    first_lock = user.locked_until
    assert first_lock is not None

    # Expire the lock so another attempt is even counted.
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    fail_login(db_session, 1)

    db_session.refresh(user)
    assert user.locked_until is not None
    second_duration = user.locked_until - datetime.now(UTC)
    assert second_duration > timedelta(seconds=60)


def test_lockout_does_not_reveal_itself_over_http(client: TestClient, user: User) -> None:
    """A locked account must answer exactly like a wrong password.

    Saying "this account is locked" would confirm the address has an account,
    undoing the enumeration resistance the login endpoint is built around.
    """
    for _ in range(MAX_FAILED_LOGIN_ATTEMPTS):
        client.post(LOGIN_URL, json={"email": EMAIL, "password": WRONG_PASSWORD})

    locked = client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    unknown = client.post(
        LOGIN_URL, json={"email": "nobody@test.com", "password": PASSWORD}
    )

    assert locked.status_code == unknown.status_code == 401
    assert locked.json() == unknown.json()


def test_lockout_is_per_account(db_session: Session, user: User) -> None:
    """Attacking one account must not lock another."""
    other = register_user(
        db_session,
        email="other@test.com",
        password=PASSWORD,
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    )

    fail_login(db_session, MAX_FAILED_LOGIN_ATTEMPTS)

    db_session.refresh(other)
    assert is_locked(other) is False
    assert (
        authenticate_user(db_session, email="other@test.com", password=PASSWORD).id
        == other.id
    )
