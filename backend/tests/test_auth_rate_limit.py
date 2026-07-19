"""Rate limiting as the auth endpoints apply it.

The limiter's own window arithmetic is covered in test_rate_limit.py; these
assert that the endpoints actually consult it, and answer correctly when they
do. The control is per caller, which is what blunts spraying one password
across many accounts — the per-account lockout in test_auth_lockout.py is a
different control against a different attack.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models.user import User, UserRole
from app.services.auth import register_user

LOGIN_URL = f"{API_V1_PREFIX}/auth/login"
REGISTER_URL = f"{API_V1_PREFIX}/auth/register"

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
    """An account to attempt sign-ins against."""
    return register_user(
        db_session,
        email=EMAIL,
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )


def test_login_is_rate_limited(client: TestClient, user: User) -> None:
    """Repeated attempts from one caller eventually get 429, not 401."""
    statuses = [
        client.post(
            LOGIN_URL, json={"email": EMAIL, "password": WRONG_PASSWORD}
        ).status_code
        for _ in range(12)
    ]

    assert 429 in statuses


def test_rate_limited_response_says_when_to_retry(client: TestClient, user: User) -> None:
    """Retry-After is what lets a client back off instead of staying blocked."""
    response = None
    for _ in range(12):
        response = client.post(
            LOGIN_URL, json={"email": EMAIL, "password": WRONG_PASSWORD}
        )
        if response.status_code == 429:
            break

    assert response is not None
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_successful_login_refunds_the_callers_budget(
    client: TestClient, user: User
) -> None:
    """A few typos must not lock someone out of their own next sign-in."""
    for _ in range(4):
        client.post(LOGIN_URL, json={"email": EMAIL, "password": WRONG_PASSWORD})

    assert (
        client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD}).status_code
        == 200
    )

    # Budget refunded, so a fresh run of attempts is available rather than an
    # immediate 429.
    assert (
        client.post(
            LOGIN_URL, json={"email": EMAIL, "password": WRONG_PASSWORD}
        ).status_code
        == 401
    )


def test_registration_is_rate_limited(client: TestClient) -> None:
    """Unlimited registration turns the 409 on a taken address into an oracle."""
    statuses = []
    for index in range(8):
        statuses.append(
            client.post(
                REGISTER_URL,
                json={
                    "email": f"new{index}@test.com",
                    "password": PASSWORD,
                    "full_name": "New Person",
                    "role": UserRole.CANDIDATE.value,
                },
            ).status_code
        )

    assert 429 in statuses


# --------------------------------------------------------------------------
# Identifying the real caller behind a proxy
# --------------------------------------------------------------------------


def test_forwarded_header_is_ignored_from_an_untrusted_peer(
    client: TestClient, user: User
) -> None:
    """A forged header must not buy a fresh budget.

    Honouring X-Forwarded-For from anyone would make the limit trivially
    bypassable: invent a new value per request and the budget never runs out.
    """
    for _ in range(12):
        response = client.post(
            LOGIN_URL,
            json={"email": EMAIL, "password": WRONG_PASSWORD},
            headers={"X-Forwarded-For": f"10.0.0.{_}"},
        )

    assert response.status_code == 429


def test_callers_behind_a_trusted_proxy_get_separate_budgets(
    valid_env: None, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The decisive property.

    Every browser request reaches the API through nginx, so without this they
    all share one bucket and ten failed logins from one person 429 everybody
    else — on a correct password. Verified before the fix: it did exactly that.
    """
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "testclient")
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    register_user(
        db_session,
        email=EMAIL,
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )

    with TestClient(app) as proxied:
        # One caller burns their whole budget.
        for _ in range(12):
            noisy = proxied.post(
                LOGIN_URL,
                json={"email": EMAIL, "password": WRONG_PASSWORD},
                headers={"X-Forwarded-For": "203.0.113.9"},
            )
        assert noisy.status_code == 429

        # A different caller through the same proxy is unaffected.
        quiet = proxied.post(
            LOGIN_URL,
            json={"email": EMAIL, "password": PASSWORD},
            headers={"X-Forwarded-For": "198.51.100.4"},
        )

    app.dependency_overrides.clear()

    assert quiet.status_code != 429


def test_only_the_rightmost_forwarded_hop_is_believed(
    valid_env: None, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A client can prepend hops; only what the proxy appended is real.

    Taking the leftmost entry would restore the bypass the trust check exists
    to prevent — a caller would simply vary the prefix each request.
    """
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "testclient")
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    register_user(
        db_session,
        email=EMAIL,
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )

    with TestClient(app) as proxied:
        # The forged prefix changes every time; the real hop does not.
        for index in range(12):
            response = proxied.post(
                LOGIN_URL,
                json={"email": EMAIL, "password": WRONG_PASSWORD},
                headers={"X-Forwarded-For": f"10.9.9.{index}, 203.0.113.9"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 429
