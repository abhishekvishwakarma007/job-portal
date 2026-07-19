"""Demo account seeding.

The entrypoint runs this on every boot, so the operation has to be safe to
repeat: a second run must not fail, duplicate accounts, or quietly reset a
password someone changed while testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.seed import SEED_USERS, SeedUser, seed_users
from app.db.session import get_db
from app.main import create_app
from app.models.user import User, UserRole
from app.services.auth import authenticate_user


def test_seeds_every_demo_account(db_session: Session) -> None:
    """A fresh database gains one account per specification."""
    created = seed_users(db_session)

    assert len(created) == len(SEED_USERS)
    assert db_session.query(User).count() == len(SEED_USERS)


def test_seeds_both_roles(db_session: Session) -> None:
    """The README promises a login per role, so both must exist.

    A reviewer following the walkthrough with only one role available cannot
    exercise the authorisation boundaries at all.
    """
    seed_users(db_session)

    roles = {user.role for user in db_session.query(User).all()}

    assert roles == {UserRole.HR, UserRole.CANDIDATE}


def test_running_twice_creates_nothing_further(db_session: Session) -> None:
    """Idempotence: the entrypoint reruns this on every container start."""
    seed_users(db_session)

    second_run = seed_users(db_session)

    assert second_run == []
    assert db_session.query(User).count() == len(SEED_USERS)


def test_rerun_does_not_reset_a_changed_password(db_session: Session) -> None:
    """An existing account is left alone, not overwritten.

    Someone mid-way through testing a password change should not find it
    silently reverted the next time the stack restarts.
    """
    seed_users(db_session)
    user = db_session.query(User).filter_by(email=SEED_USERS[0].email).one()
    user.hashed_password = "$2b$12$" + "x" * 53
    db_session.commit()

    seed_users(db_session)

    db_session.refresh(user)
    assert user.hashed_password.endswith("x" * 53)


@pytest.mark.parametrize("spec", SEED_USERS, ids=lambda spec: spec.email)
def test_seeded_accounts_can_actually_authenticate(
    db_session: Session, spec: SeedUser
) -> None:
    """The documented credentials must really work.

    Asserted through the same service the login endpoint uses, so a seed that
    stored a malformed hash fails here rather than in a reviewer's browser.
    """
    seed_users(db_session)

    user = authenticate_user(db_session, email=spec.email, password=spec.password)

    assert user.email == spec.email


def test_seeded_passwords_are_hashed(db_session: Session) -> None:
    """No demo account may store a recoverable password."""
    seed_users(db_session)

    for spec in SEED_USERS:
        user = db_session.query(User).filter_by(email=spec.email).one()
        assert user.hashed_password != spec.password
        assert verify_password(spec.password, user.hashed_password)


def test_seeded_emails_are_normalised(db_session: Session) -> None:
    """Seeded addresses must obey the same lower-casing as registered ones."""
    seed_users(db_session)

    stored = db_session.execute(select(func.lower(User.email))).scalars().all()

    assert all(email == email.lower() for email in stored)


def test_seeded_accounts_are_active(db_session: Session) -> None:
    """A demo account that is disabled on arrival is useless to a reviewer."""
    seed_users(db_session)

    assert all(user.is_active for user in db_session.query(User).all())


def test_seed_specifications_are_distinct() -> None:
    """Two specs sharing an address would make the seed order-dependent."""
    emails = [spec.email for spec in SEED_USERS]

    assert len(emails) == len(set(emails))


@pytest.mark.parametrize("spec", SEED_USERS, ids=lambda spec: spec.email)
def test_seeded_credentials_are_accepted_by_the_login_endpoint(
    valid_env: None, db_session: Session, spec: SeedUser
) -> None:
    """The documented credentials must work through HTTP, not just the service.

    Regression test. The seed originally used @jobportal.test addresses, which
    the service layer accepted happily — but EmailStr refuses .test as a
    special-use TLD, so every documented login died with a 422 at the API
    boundary while every service-level test still passed. Exercising the real
    endpoint is the only thing that catches a mismatch between what the seed
    writes and what the schema will accept back.
    """
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    seed_users(db_session)

    with TestClient(app) as client:
        response = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": spec.email, "password": spec.password},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]
