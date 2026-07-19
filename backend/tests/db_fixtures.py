"""Fixtures giving each test a clean, real Postgres schema.

Deliberately not SQLite: the schema relies on Postgres-native enums, UUID
columns, and server-side defaults, so a SQLite stand-in would pass tests that
production would fail. The database comes from `docker compose up db`.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base

# Points at the compose `db` service published on localhost. Overridable via
# TEST_DATABASE_URL so the same suite can run inside the Docker network later,
# where the host is `db` rather than localhost.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://jobportal:jobportal@localhost:5432/jobportal_test"
)


def _test_database_url() -> str:
    """Resolve the test database URL, preferring an explicit override."""
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Session-scoped engine with the schema created once up front.

    Creating tables per-test would dominate runtime; per-test isolation comes
    from truncation instead (see `db_session`).
    """
    url = _test_database_url()
    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            connection.close()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(
            f"No test database reachable at {url} ({exc.__class__.__name__}). "
            "Start it with: docker compose up -d db"
        )

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
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
