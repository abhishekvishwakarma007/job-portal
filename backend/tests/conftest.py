"""Shared fixtures.

Config is read from the process environment, so every test that touches
settings must start from a known-clean slate — otherwise the developer's
real shell env leaks in and makes the fail-fast tests pass for the wrong
reason.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Minimum viable env for a Settings() instance to construct successfully.
VALID_ENV: dict[str, str] = {
    "SECRET_KEY": "a" * 32,
    "DATABASE_URL": "postgresql+psycopg://user:pw@localhost:5432/jobportal",
}

# Seeded at conftest import — i.e. before pytest imports any test module, and
# therefore before `app.main` runs `create_app()` at module level. Without this
# bootstrap, collection itself would die on a config ValidationError. Per-test
# fixtures below still control the environment; this only unblocks import.
for _key, _value in VALID_ENV.items():
    os.environ.setdefault(_key, _value)
os.environ.setdefault("ENVIRONMENT", "test")

# Every var Settings reads. Cleared wholesale before each test.
_MANAGED_VARS = (
    "SECRET_KEY",
    "DATABASE_URL",
    "ENVIRONMENT",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove all app-managed env vars so each test controls its own config."""
    for var in _MANAGED_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Populate the environment with a complete, valid configuration."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture(autouse=True)
def _no_dotenv_leak(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Run each test from an empty directory so no real .env is ever read.

    Settings declares `env_file=".env"`, resolved relative to the working
    directory. A developer's own backend/.env would otherwise supply values the
    fail-fast tests are trying to prove are absent — making them pass against a
    broken implementation. Verified by test_dotenv_is_not_loaded_during_tests.
    """
    monkeypatch.chdir(tmp_path)
    yield
