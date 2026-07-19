"""User model behaviour, asserted against a real Postgres schema.

The constraints here are security boundaries, not conveniences: a duplicate
email splits one identity across two accounts, and a role outside the enum
would silently bypass every authorisation gate built on it.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User, UserRole

HASHED_PASSWORD = "$2b$12$" + "x" * 53  # shaped like bcrypt output, never real


def make_user(email: str = "hr@test.com", role: UserRole = UserRole.HR) -> User:
    """Build an unsaved User with valid defaults."""
    return User(
        email=email,
        hashed_password=HASHED_PASSWORD,
        full_name="Test Person",
        role=role,
    )


def test_persists_user_with_generated_id_and_timestamps(db_session: Session) -> None:
    """Happy path: a saved user gets a UUID id and server-side timestamps."""
    user = make_user()
    db_session.add(user)
    db_session.commit()

    assert isinstance(user.id, uuid.UUID)
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_is_active_defaults_to_true(db_session: Session) -> None:
    """New accounts are usable immediately; deactivation is an explicit act."""
    user = make_user()
    db_session.add(user)
    db_session.commit()

    assert user.is_active is True


@pytest.mark.parametrize("role", [UserRole.HR, UserRole.CANDIDATE])
def test_accepts_both_valid_roles(db_session: Session, role: UserRole) -> None:
    """Both roles in the system must round-trip through the DB enum."""
    user = make_user(email=f"{role.value.lower()}@test.com", role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.role is role


def test_rejects_role_outside_the_enum(db_session: Session) -> None:
    """An unknown role must be refused by Postgres, not coerced or stored.

    Every authorisation check keys off this column, so a value the code does
    not recognise would land in an undefined authorisation state.
    """
    db_session.add(make_user())
    db_session.commit()

    with pytest.raises((DataError, IntegrityError)):
        db_session.execute(
            text("UPDATE users SET role = 'SUPERADMIN' WHERE email = 'hr@test.com'")
        )
        db_session.commit()


def test_duplicate_email_rejected_by_database(db_session: Session) -> None:
    """A second account on the same email must fail at the DB level.

    Enforced by a UNIQUE constraint rather than a service-layer pre-check, so
    two concurrent registrations cannot both pass the check and both insert.
    """
    db_session.add(make_user(email="dupe@test.com"))
    db_session.commit()

    db_session.add(make_user(email="dupe@test.com", role=UserRole.CANDIDATE))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_uniqueness_is_case_insensitive(db_session: Session) -> None:
    """Mixed-case duplicates must collide with the original.

    Without normalisation "Admin@test.com" and "admin@test.com" are distinct
    to the UNIQUE index, letting one person hold two accounts for the same
    inbox and apply to a job twice.
    """
    db_session.add(make_user(email="admin@test.com"))
    db_session.commit()

    db_session.add(make_user(email="Admin@Test.com", role=UserRole.CANDIDATE))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_case_insensitive_uniqueness_survives_raw_sql(db_session: Session) -> None:
    """A mixed-case duplicate must fail even when the ORM is bypassed.

    The `@validates` normaliser only runs on the ORM path, so a seed script,
    bulk import, or admin psql session could otherwise insert "HR@Demo.com"
    beside "hr@demo.com" and give one person two accounts for one inbox. This
    asserts the guarantee lives in the database, not just in Python.
    """
    db_session.add(make_user(email="raw@test.com"))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, full_name, role) "
                "VALUES (gen_random_uuid(), 'RAW@Test.COM', :pw, 'Case Twin', 'HR')"
            ),
            {"pw": HASHED_PASSWORD},
        )
        db_session.commit()


def test_email_is_normalised_on_write(db_session: Session) -> None:
    """Surrounding whitespace and case are stripped before storage."""
    user = make_user(email="  MiXeD@Test.COM  ")
    db_session.add(user)
    db_session.commit()

    stored = db_session.execute(text("SELECT email FROM users")).scalar_one()
    assert stored == "mixed@test.com"


def test_has_no_plaintext_password_column(db_engine: Engine) -> None:
    """Only a hash column may exist — no place for a plaintext value to land."""
    columns = {column["name"] for column in inspect(db_engine).get_columns("users")}

    assert "hashed_password" in columns
    assert "password" not in columns
    assert "plain_password" not in columns


def test_repr_does_not_leak_password_hash(db_session: Session) -> None:
    """The hash must never reach a log line via an accidental repr()."""
    user = make_user()
    db_session.add(user)
    db_session.commit()

    assert HASHED_PASSWORD not in repr(user)


def test_email_and_role_are_not_nullable(db_engine: Engine) -> None:
    """Identity and authorisation columns must never be null."""
    user_columns = {
        column["name"]: column for column in inspect(db_engine).get_columns("users")
    }

    assert user_columns["email"]["nullable"] is False
    assert user_columns["role"]["nullable"] is False
    assert user_columns["hashed_password"]["nullable"] is False
