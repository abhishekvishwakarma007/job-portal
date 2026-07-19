"""Registration, login, and the current-user endpoint.

The failure cases carry as much weight as the happy path here: a login that
distinguishes "wrong password" from "no such account" hands an attacker a
membership oracle, and a token trusted without re-reading the user lets a
disabled account keep working until it expires.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.user import User, UserRole

REGISTER_URL = f"{API_V1_PREFIX}/auth/register"
LOGIN_URL = f"{API_V1_PREFIX}/auth/login"
ME_URL = f"{API_V1_PREFIX}/auth/me"

PASSWORD = "correct-horse-battery-staple-7"


def registration_payload(**overrides: Any) -> dict[str, Any]:
    """A valid registration body, with fields overridable per test."""
    payload: dict[str, Any] = {
        "email": "hr@test.com",
        "password": PASSWORD,
        "full_name": "Dana HR",
        "role": UserRole.HR.value,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def client(valid_env: None, db_session: Session) -> Iterator[TestClient]:
    """A TestClient whose requests share the test's transaction.

    get_db is overridden rather than letting the app build its own session, so
    assertions can read rows the request just wrote.
    """
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def register(client: TestClient, **overrides: Any) -> Any:
    """Register a user and return the raw response."""
    return client.post(REGISTER_URL, json=registration_payload(**overrides))


def login(client: TestClient, email: str, password: str) -> Any:
    """Attempt a login and return the raw response."""
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def auth_header(token: str) -> dict[str, str]:
    """Build the Authorization header for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_register_creates_the_account(client: TestClient) -> None:
    """Happy path: a valid body yields 201 and the created user."""
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "hr@test.com"
    assert body["role"] == UserRole.HR.value
    assert body["is_active"] is True
    assert body["id"]


def test_register_never_returns_password_material(client: TestClient) -> None:
    """Neither the plaintext nor the hash may appear in the response.

    Returning the hash would hand an attacker who achieves any read primitive
    something to crack offline at leisure.
    """
    body = register(client).json()

    serialised = str(body)
    assert PASSWORD not in serialised
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_stores_a_hash_not_the_plaintext(
    client: TestClient, db_session: Session
) -> None:
    """The database must never hold a recoverable password."""
    register(client)

    stored = db_session.execute(text("SELECT hashed_password FROM users")).scalar_one()

    assert stored != PASSWORD
    assert stored.startswith("$2b$")


def test_register_rejects_a_duplicate_email(client: TestClient) -> None:
    """A second account on one address must be refused, not silently created."""
    register(client)

    response = register(client)

    assert response.status_code == 409


def test_register_rejects_a_case_variant_duplicate(
    client: TestClient, db_session: Session
) -> None:
    """ "HR@Test.com" is the same inbox as "hr@test.com" and must collide."""
    register(client, email="hr@test.com")

    response = register(client, email="HR@Test.com")

    assert response.status_code == 409
    assert db_session.execute(text("SELECT count(*) FROM users")).scalar_one() == 1


def test_register_normalises_the_stored_email(
    client: TestClient, db_session: Session
) -> None:
    """Mixed case and stray whitespace must not reach the database."""
    register(client, email="  MiXeD@Test.COM  ")

    stored = db_session.execute(text("SELECT email FROM users")).scalar_one()

    assert stored == "mixed@test.com"


@pytest.mark.parametrize(
    "password",
    [
        "short",  # below the length floor
        "alllowercaseletters",  # one class only
        "1234567890123456",  # one class only
        "password1",  # two classes — the shape a dictionary attack starts from
        "PASSWORD1",  # two classes
    ],
)
def test_register_rejects_a_weak_password(client: TestClient, password: str) -> None:
    """The strength policy is enforced server-side, not only in the browser."""
    response = register(client, password=password)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    [
        "Admin@1234",  # the credentials the brief publishes
        "User@1234",
        "Passw0rd",  # exactly at the floor, three classes
        "correct-horse-battery-staple-7",  # long passphrase, no capital
    ],
)
def test_register_accepts_a_sufficiently_varied_password(
    client: TestClient, password: str
) -> None:
    """The policy must not reject credentials people are actually told to use.

    A long passphrase with no capital is stronger than a short mixed-case
    string, so requiring three of four classes rather than all four keeps it
    usable without weakening the rule against single-class passwords.
    """
    response = register(client, password=password)

    assert response.status_code == 201, response.text


def test_register_rejects_a_password_beyond_the_bcrypt_limit(
    client: TestClient,
) -> None:
    """Past 72 bytes bcrypt truncates, so two different passwords would collide."""
    response = register(client, password="a1" * 40)

    assert response.status_code == 422


@pytest.mark.parametrize("email", ["not-an-email", "@test.com", "spaces in@test.com"])
def test_register_rejects_an_invalid_email(client: TestClient, email: str) -> None:
    """Malformed addresses are refused at the boundary."""
    assert register(client, email=email).status_code == 422


def test_register_rejects_an_unknown_role(client: TestClient) -> None:
    """Only the two defined roles exist; anything else must not be creatable."""
    assert register(client, role="SUPERADMIN").status_code == 422


def test_register_ignores_client_supplied_privileged_fields(
    client: TestClient, db_session: Session
) -> None:
    """Mass-assignment guard: the client must not be able to set is_active.

    A registration body that could flip server-controlled columns would let a
    caller create an account in a state the server never intended.
    """
    client.post(
        REGISTER_URL,
        json=registration_payload(
            is_active=False, id="00000000-0000-0000-0000-000000000001"
        ),
    )

    user = db_session.query(User).one()
    assert user.is_active is True
    assert str(user.id) != "00000000-0000-0000-0000-000000000001"


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


def test_login_returns_a_bearer_token(client: TestClient) -> None:
    """Happy path: correct credentials yield a usable token."""
    register(client)

    response = login(client, "hr@test.com", PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_accepts_a_differently_cased_email(client: TestClient) -> None:
    """Someone who typed their address with capitals must still get in."""
    register(client, email="hr@test.com")

    assert login(client, "HR@Test.COM", PASSWORD).status_code == 200


def test_login_rejects_a_wrong_password(client: TestClient) -> None:
    """The core negative case."""
    register(client)

    assert login(client, "hr@test.com", "wrong-password-9").status_code == 401


def test_login_rejects_an_unknown_email(client: TestClient) -> None:
    """No account means no token."""
    assert login(client, "nobody@test.com", PASSWORD).status_code == 401


def test_login_does_not_reveal_whether_an_account_exists(client: TestClient) -> None:
    """Wrong password and unknown email must be indistinguishable.

    Any difference in status or body turns the endpoint into an oracle for
    which addresses hold accounts — useful for targeting a phishing campaign,
    and a disclosure in its own right.
    """
    register(client, email="hr@test.com")

    wrong_password = login(client, "hr@test.com", "wrong-password-9")
    unknown_email = login(client, "nobody@test.com", PASSWORD)

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_rejects_a_deactivated_account(
    client: TestClient, db_session: Session
) -> None:
    """Disabling an account must take effect at the next login attempt."""
    register(client)
    db_session.query(User).update({User.is_active: False})
    db_session.commit()

    assert login(client, "hr@test.com", PASSWORD).status_code == 401


# --------------------------------------------------------------------------
# Current user
# --------------------------------------------------------------------------


def test_me_returns_the_authenticated_user(client: TestClient) -> None:
    """A valid token identifies its owner."""
    register(client)
    token = login(client, "hr@test.com", PASSWORD).json()["access_token"]

    response = client.get(ME_URL, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == "hr@test.com"
    assert response.json()["role"] == UserRole.HR.value


def test_me_requires_a_token(client: TestClient) -> None:
    """The endpoint is not public."""
    assert client.get(ME_URL).status_code == 401


def test_me_rejects_a_malformed_token(client: TestClient) -> None:
    """Garbage in the header must not reach the database layer."""
    assert client.get(ME_URL, headers=auth_header("not.a.jwt")).status_code == 401


def test_me_rejects_a_token_for_a_user_that_no_longer_exists(
    client: TestClient, db_session: Session
) -> None:
    """A validly-signed token for a deleted account must not authenticate."""
    register(client)
    token = login(client, "hr@test.com", PASSWORD).json()["access_token"]
    db_session.query(User).delete()
    db_session.commit()

    assert client.get(ME_URL, headers=auth_header(token)).status_code == 401


def test_me_rejects_a_token_for_a_deactivated_user(
    client: TestClient, db_session: Session
) -> None:
    """Deactivation must lock the account out immediately.

    The user is re-read on every request precisely so that disabling an account
    does not wait for the token to expire — otherwise a dismissed employee
    keeps HR access for the remainder of the token's lifetime.
    """
    register(client)
    token = login(client, "hr@test.com", PASSWORD).json()["access_token"]
    db_session.query(User).update({User.is_active: False})
    db_session.commit()

    assert client.get(ME_URL, headers=auth_header(token)).status_code == 401


def test_me_rejects_a_forged_token_for_a_real_user(
    client: TestClient, db_session: Session
) -> None:
    """A token minted with the wrong key must not authenticate a real account."""
    register(client)
    user = db_session.query(User).one()

    forged = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "exp": 9999999999},
        "an-attackers-own-signing-key-32-chars",
        algorithm="HS256",
    )

    assert client.get(ME_URL, headers=auth_header(forged)).status_code == 401


def test_me_role_comes_from_the_database_not_the_token(
    client: TestClient, db_session: Session
) -> None:
    """A stale role claim must not outrank the stored one.

    Someone whose role was downgraded still holds a token asserting the old
    one; the response must reflect the database.
    """
    register(client, role=UserRole.HR.value)
    token = login(client, "hr@test.com", PASSWORD).json()["access_token"]

    db_session.query(User).update({User.role: UserRole.CANDIDATE})
    db_session.commit()

    response = client.get(ME_URL, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.CANDIDATE.value


def test_me_rejects_an_expired_token(client: TestClient, db_session: Session) -> None:
    """An expired token must not authenticate even though it is correctly signed."""
    register(client)
    user = db_session.query(User).one()

    expired = create_access_token(
        user_id=user.id,
        role=user.role,
        expires_delta=timedelta(seconds=-1),
    )

    assert client.get(ME_URL, headers=auth_header(expired)).status_code == 401
