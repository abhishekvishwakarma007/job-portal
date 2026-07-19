"""Fixtures giving each test a clean, real Postgres schema.

Deliberately not SQLite: the schema relies on Postgres-native enums, UUID
columns, and server-side defaults, so a SQLite stand-in would pass tests that
production would fail. The database comes from `docker compose up db`.

The schema is built by running the Alembic migrations, not by create_all, so
the tests exercise the exact schema production will have. Under create_all a
migration that drifted from the models would leave every test green while the
deployed database was wrong.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config
from app.db.base import Base

# alembic.ini sits at the backend root, two levels up from tests/.
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

# Points at the compose `db` service published on localhost. Overridable via
# TEST_DATABASE_URL so the same suite can run inside the Docker network later,
# where the host is `db` rather than localhost.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://jobportal:jobportal@localhost:5432/jobportal_test"
)

# Enforced by _require_test_database before anything destructive runs.
TEST_DATABASE_SUFFIX = "_test"

# Arbitrary constant identifying this suite's advisory lock. Any concurrent
# pytest process against the same database waits on it rather than racing.
_SUITE_LOCK_ID = 4_812_007


def _acquire_exclusive_lock(engine: Engine) -> Connection:
    """Hold a Postgres advisory lock for the lifetime of the test session.

    Two pytest processes pointed at one test database will destroy each other:
    this fixture drops and recreates the public schema, so a second run wiping
    the schema mid-suite makes rows a first run just committed disappear — which
    surfaces as a baffling "could not refresh instance" rather than anything
    that names the real cause.

    The lock serialises them instead. A concurrent run blocks here until the
    first finishes rather than corrupting it. Session-level (not
    transaction-level) so it is held across every transaction the suite opens,
    and released when this connection closes.
    """
    connection = engine.connect()
    connection.execute(text(f"SELECT pg_advisory_lock({_SUITE_LOCK_ID})"))
    # Commit so the lock is not sitting inside an open transaction that later
    # statements would extend.
    connection.commit()
    return connection


def _test_database_url() -> str:
    """Resolve the test database URL, preferring an explicit override."""
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def _require_test_database(url: str) -> None:
    """Abort unless the URL names a database reserved for tests.

    The fixture below drops the entire public schema. Pointing TEST_DATABASE_URL
    at the development database by mistake would silently destroy it, so refuse
    anything whose database name does not end in the required suffix.
    """
    database_name = urlsplit(url).path.lstrip("/")
    if not database_name.endswith(TEST_DATABASE_SUFFIX):
        raise RuntimeError(
            f"Refusing to run the suite against {database_name!r}: the test "
            f"database name must end in {TEST_DATABASE_SUFFIX!r}, because the "
            "fixtures drop and recreate its schema."
        )


def _alembic_config(url: str) -> Config:
    """Build an Alembic config pinned to the test database.

    Setting the URL here is what stops env.py falling back to the application's
    own DATABASE_URL — otherwise migrations would run against the development
    database and the suite would drop its tables.
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    # alembic.ini gives script_location as a relative path, which breaks under
    # the autouse fixture that runs each test from a temp directory. Resolve it
    # against the backend root so cwd stops mattering.
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return config


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Session-scoped engine with the schema migrated once up front.

    Migrating per-test would dominate runtime; per-test isolation comes from
    truncation instead (see `db_session`).
    """
    url = _test_database_url()
    _require_test_database(url)
    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            connection.close()
    except Exception as exc:  # pragma: no cover - environment guard
        # Fail, not skip. Skipping means most of the suite silently disappears
        # and `pytest -q` still prints a row of dots — a green run that proved
        # nothing. Someone following the README without starting the database
        # should be told, not congratulated.
        pytest.fail(
            f"No test database reachable at {url} "
            f"({exc.__class__.__name__}). "
            "Start it first:  docker compose up -d db",
            pytrace=False,
        )

    # Serialise against any other pytest process on this database before
    # touching the schema. Held until the session ends.
    lock_connection = _acquire_exclusive_lock(engine)

    # Drop the schema outright rather than downgrading: an interrupted run, or
    # one that predates Alembic, can leave tables and enum types behind with no
    # alembic_version row to downgrade from, and `upgrade` would then collide
    # with the objects already there. _require_test_database above is what makes
    # this safe to do unconditionally.
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    command.upgrade(_alembic_config(url), "head")

    yield engine

    # Closing releases the advisory lock, letting any waiting run proceed.
    lock_connection.close()
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Yield a Session against a truncated schema.

    Every table is emptied before the test runs, so tests are order-independent
    and a leftover row from one can never satisfy another's assertions.
    RESTART IDENTITY also resets sequences so IDs stay predictable.
    """
    table_names = ", ".join(
        f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables)
    )
    if table_names:
        with db_engine.begin() as connection:
            connection.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )

    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
