"""Engine and session lifecycle.

The engine is built lazily and cached, so importing this module never opens a
socket — which keeps unit tests runnable without a live database.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# Recycle below the typical 5-minute idle cutoff on managed Postgres so we
# never hand a request a connection the server has already dropped.
POOL_RECYCLE_SECONDS = 280
POOL_SIZE = 5
MAX_OVERFLOW = 10


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide Engine, created on first use."""
    settings = get_settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # cheap liveness check; avoids stale-connection 500s
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory, created on first use."""
    return sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,  # keeps ORM objects usable after commit
    )


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped Session, closing it however the request ends.

    FastAPI dependency. The `finally` is what matters: without it an exception
    raised mid-request would leak the connection and eventually drain the pool.

    Typed as Generator rather than Iterator because callers legitimately drive
    close()/throw() on it — FastAPI does exactly this to unwind the dependency
    when a handler raises.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
