"""Application configuration, validated at import time.

Every setting is validated the moment the process boots. A container with a
bad config must crash on startup — never serve traffic in a degraded state
where, for example, tokens are signed with a guessable default key.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# A signing key shorter than this is brute-forceable offline once an attacker
# holds a single issued token. 32 bytes matches the HS256 output width.
MIN_SECRET_KEY_LENGTH = 32

# Substrings that betray a copy-pasted example key. Checked case-insensitively
# because "CHANGEME" is just as dangerous as "changeme".
PLACEHOLDER_SECRET_MARKERS = ("changeme", "secret-key", "your-secret", "example", "xxxx")

# The models use Postgres-specific column types and constraints, so any other
# driver would fail at migration time — better to reject it at boot.
ALLOWED_DB_SCHEMES = ("postgresql://", "postgresql+psycopg://", "postgresql+asyncpg://")

DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]

# Hosts whose X-Forwarded-For we are willing to believe. Empty by default:
# the header is attacker-supplied unless a proxy we control overwrites it.
DEFAULT_TRUSTED_PROXY_HOSTS: list[str] = []
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 15

# Long enough that a person is not signed out mid-week, short enough that a
# stolen token stops working while the theft is still recent. Rotation on every
# use is what keeps the window narrow in practice.
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7


class Environment(StrEnum):
    """Deployment environment. Gates debug-only behavior such as /docs."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Fields without defaults are mandatory: omitting one raises ValidationError
    before the FastAPI app is ever constructed.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    secret_key: str
    database_url: str
    environment: Environment = Environment.DEVELOPMENT

    access_token_expire_minutes: int = Field(
        default=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES, gt=0
    )
    refresh_token_expire_days: int = Field(
        default=DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS, gt=0
    )
    # NoDecode opts out of pydantic-settings' default JSON parsing for complex
    # types, so the validator below can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    # Reverse proxies permitted to identify the real client. Everything behind
    # nginx arrives from one address, so without this the per-caller rate limit
    # degrades into a single bucket shared by every user.
    trusted_proxy_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_TRUSTED_PROXY_HOSTS)
    )

    @field_validator("secret_key")
    @classmethod
    def _reject_weak_secret_key(cls, value: str) -> str:
        """Reject keys that are too short or recognisably a placeholder."""
        if len(value) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters, "
                f"got {len(value)}"
            )

        lowered = value.lower()
        if any(marker in lowered for marker in PLACEHOLDER_SECRET_MARKERS):
            raise ValueError(
                "SECRET_KEY looks like a placeholder; generate one with "
                "`python -c 'import secrets; print(secrets.token_urlsafe(32))'`"
            )

        return value

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, value: str) -> str:
        """Reject any driver other than Postgres, which the schema requires."""
        if not value.startswith(ALLOWED_DB_SCHEMES):
            raise ValueError(
                f"DATABASE_URL must use one of {ALLOWED_DB_SCHEMES}, got {value!r}"
            )

        return value

    @field_validator("cors_origins", "trusted_proxy_hosts", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """Accept `a.com, b.com` from the environment and split it into a list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @property
    def is_production(self) -> bool:
        """True when running in production, where debug surfaces stay closed."""
        return self.environment is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings, parsed once on first access.

    Cached so that request handlers depending on this never re-read the
    environment. Tests call `get_settings.cache_clear()` to rebuild it.
    """
    return Settings()
