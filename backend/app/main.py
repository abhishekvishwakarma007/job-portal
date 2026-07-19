"""FastAPI application factory.

Built as a factory rather than a module-level singleton so tests can construct
an app against a controlled environment instead of whatever was set at import.
"""

from typing import Any

from fastapi import FastAPI, Request, Response
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

    `allow_credentials` is off: both tokens travel in the Authorization header
    and in the response body, never in a cookie, so nothing here needs
    credentialed requests. Enabling it anyway would widen what a browser will
    send cross-origin in exchange for nothing — and an earlier version of this
    comment justified it with a cookie that does not exist.

    The origin list stays explicit regardless.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
    )


# Applied to every API response. nginx sets these for the SPA it serves, but
# the API is reachable directly on its own port — the README even points at
# :8000/docs — and that origin had none of them.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # The API serves JSON, not documents, so nothing legitimate needs to be
    # framed, scripted, or loaded from elsewhere.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def _configure_security_headers(app: FastAPI) -> None:
    """Add the response headers a browser acts on.

    Excludes /docs and /redoc, whose Swagger UI legitimately loads scripts and
    styles from a CDN — the restrictive CSP above would leave a blank page. The
    interactive docs are disabled in production anyway.
    """

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)

        if request.url.path not in {"/docs", "/redoc", "/openapi.json"}:
            for header, value in SECURITY_HEADERS.items():
                response.headers.setdefault(header, value)

        return response


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
    _configure_security_headers(app)
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
