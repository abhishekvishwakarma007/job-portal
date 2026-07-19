"""Config must fail fast and loudly — a misconfigured app should never boot.

The threat model: a deploy that silently falls back to a default signing key
mints tokens any attacker can forge. Every test here asserts we crash instead.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from tests.conftest import VALID_ENV


def test_loads_valid_configuration(valid_env: None) -> None:
    """Happy path: a complete environment produces a usable Settings object."""
    settings = Settings()

    assert settings.secret_key == VALID_ENV["SECRET_KEY"]
    assert settings.database_url == VALID_ENV["DATABASE_URL"]


def test_missing_secret_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """No SECRET_KEY must abort startup rather than fall back to a default."""
    monkeypatch.setenv("DATABASE_URL", VALID_ENV["DATABASE_URL"])

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "secret_key" in str(exc_info.value).lower()


def test_missing_database_url_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """No DATABASE_URL must abort startup rather than silently use SQLite."""
    monkeypatch.setenv("SECRET_KEY", VALID_ENV["SECRET_KEY"])

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "database_url" in str(exc_info.value).lower()


@pytest.mark.parametrize("weak_key", ["", "short", "a" * 31])
def test_rejects_secret_key_below_minimum_length(
    monkeypatch: pytest.MonkeyPatch, weak_key: str
) -> None:
    """A key shorter than 32 chars is brute-forceable and must be rejected."""
    monkeypatch.setenv("SECRET_KEY", weak_key)
    monkeypatch.setenv("DATABASE_URL", VALID_ENV["DATABASE_URL"])

    with pytest.raises(ValidationError):
        Settings()


def test_rejects_placeholder_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copy-pasted placeholder keys are a known deploy footgun — reject them."""
    monkeypatch.setenv("SECRET_KEY", "changeme" * 4)  # 32 chars, still a placeholder
    monkeypatch.setenv("DATABASE_URL", VALID_ENV["DATABASE_URL"])

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "bad_url",
    [
        "sqlite:///./dev.db",
        "mysql://user:pw@localhost/db",
        "not-a-url",
    ],
)
def test_rejects_non_postgres_database_url(
    monkeypatch: pytest.MonkeyPatch, bad_url: str
) -> None:
    """The schema targets Postgres; any other driver must fail at boot."""
    monkeypatch.setenv("SECRET_KEY", VALID_ENV["SECRET_KEY"])
    monkeypatch.setenv("DATABASE_URL", bad_url)

    with pytest.raises(ValidationError):
        Settings()


def test_cors_origins_parsed_into_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS is an allow-list, so the comma-separated env var must become a list."""
    monkeypatch.setenv("SECRET_KEY", VALID_ENV["SECRET_KEY"])
    monkeypatch.setenv("DATABASE_URL", VALID_ENV["DATABASE_URL"])
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://localhost:3000")

    assert Settings().cors_origins == [
        "http://localhost:5173",
        "http://localhost:3000",
    ]


def test_dotenv_is_not_loaded_during_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's real backend/.env must never reach the test suite.

    Regression guard: the isolation fixture once chdir'd *into* the directory
    holding .env instead of away from it, so every fail-fast test above silently
    read live config and would have passed against a validation-free Settings.
    """
    monkeypatch.setenv("SECRET_KEY", VALID_ENV["SECRET_KEY"])
    dotenv_in_scope = Path.cwd() / ".env"

    assert not dotenv_in_scope.exists(), (
        f"tests are running from {Path.cwd()}, which contains a .env; "
        "config isolation is broken"
    )

    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_is_cached(valid_env: None) -> None:
    """Settings are read once at boot; repeated calls must not re-parse env."""
    get_settings.cache_clear()

    assert get_settings() is get_settings()
