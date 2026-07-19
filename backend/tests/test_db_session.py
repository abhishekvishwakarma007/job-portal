"""The get_db dependency must always release its connection.

A leaked session exhausts the pool under load, so the close-on-exception path
is asserted explicitly rather than assumed.

Closure is verified by spying on Session.close rather than reading
Session.is_active: in SQLAlchemy 2.0 `is_active` reports "not in partial
rollback state" and remains True on a closed session, so it would pass even
against an implementation that never closed anything.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db, get_engine, get_session_factory


@pytest.fixture(autouse=True)
def _configured(valid_env: None) -> Iterator[None]:
    """get_db builds its engine from settings, so config must be present.

    Caches are cleared on both sides of the test so a session-scoped engine
    built against one config never leaks into another test.
    """
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def close_calls(monkeypatch: pytest.MonkeyPatch) -> list[Session]:
    """Record every Session.close() call without suppressing the real close."""
    calls: list[Session] = []
    original = Session.close

    def spy(self: Session) -> None:
        calls.append(self)
        original(self)

    monkeypatch.setattr(Session, "close", spy)
    return calls


def test_get_db_yields_a_session(close_calls: list[Session]) -> None:
    """The dependency hands the caller a real SQLAlchemy Session."""
    generator = get_db()
    session = next(generator)

    assert isinstance(session, Session)

    generator.close()


def test_get_db_closes_session_on_success(close_calls: list[Session]) -> None:
    """Normal completion must return the connection to the pool."""
    generator = get_db()
    session = next(generator)

    with pytest.raises(StopIteration):
        next(generator)

    assert session in close_calls


def test_get_db_closes_session_on_exception(close_calls: list[Session]) -> None:
    """An error mid-request must still close the session — no pool leak."""
    generator = get_db()
    session = next(generator)

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("request blew up"))

    assert session in close_calls


def test_engine_is_created_lazily_and_cached() -> None:
    """Importing the module must not open a socket; the engine is built once."""
    assert get_engine() is get_engine()


def test_engine_uses_configured_database_url() -> None:
    """The engine must target the configured DB, not a hardcoded fallback."""
    assert get_engine().url.database == "jobportal"
    assert get_engine().url.get_backend_name() == "postgresql"
