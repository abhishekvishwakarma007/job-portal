"""FastAPI application factory.

Built as a factory rather than a module-level singleton so tests can construct
an app against a controlled environment instead of whatever was set at import.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings

APP_TITLE = "JobPortal API"
APP_VERSION = "0.1.0"
HEALTH_PATH = "/health"

# Methods and headers the SPA actually sends. Enumerated rather than "*" so a
# compromised origin cannot exercise verbs the frontend never uses.
CORS_ALLOWED_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Authorization", "Content-Type"]


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    """Apply the CORS allow-list from config.

    `allow_credentials` is on because refresh tokens travel in a cookie, which
    is precisely why the origin list must stay explicit — the wildcard is
    invalid alongside credentials and would silently break the SPA.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and wire the application.

    Interactive docs are disabled in production so the full API surface is not
    advertised to unauthenticated visitors.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    _configure_cors(app, settings)
    app.include_router(api_router)

    @app.get(HEALTH_PATH, tags=["meta"], summary="Liveness probe")
    def health() -> dict[str, Any]:
        """Report process liveness for the Docker healthcheck.

        Deliberately does not touch the database: this answers "is the process
        up", and compose gates the backend on Postgres's own healthcheck.
        """
        return {"status": "ok", "version": APP_VERSION}

    return app


app = create_app()
