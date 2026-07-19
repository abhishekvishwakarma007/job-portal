"""App wiring: health probe, router mounting, and CORS allow-list.

Docker healthchecks depend on /health, and the compose file gates the
backend on it — so these assertions protect the startup contract.
"""

from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.api.v1.router import API_V1_PREFIX
from app.api.v1.routes import applications, auth, jobs
from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client(valid_env: None) -> TestClient:
    """A TestClient over a freshly built app bound to the test environment."""
    get_settings.cache_clear()
    return TestClient(create_app())


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    """The Docker healthcheck polls this; it must be 200 with a status body."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_endpoint_requires_no_auth(client: TestClient) -> None:
    """The probe runs before any credentials exist, so it must stay public."""
    assert client.get("/health").status_code == 200


def test_openapi_schema_is_served(client: TestClient) -> None:
    """The README points reviewers at /docs — the schema must actually build."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"]


@pytest.mark.parametrize(
    ("module", "expected_prefix"),
    [(auth, "/auth"), (jobs, "/jobs"), (applications, "/applications")],
)
def test_feature_router_prefixes(module: ModuleType, expected_prefix: str) -> None:
    """Pin each feature's URL segment; the frontend client is generated off these.

    Asserted on the router objects rather than the OpenAPI paths because the
    routers carry no endpoints yet — those arrive with their feature slices.
    """
    assert module.router.prefix == expected_prefix


def test_api_version_prefix_is_stable() -> None:
    """The versioned prefix is a published contract — changing it breaks clients."""
    assert API_V1_PREFIX == "/api/v1"


def test_cors_allow_list_rejects_unknown_origin(client: TestClient) -> None:
    """An origin outside the allow-list must not receive an ACAO header."""
    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in {key.lower() for key in response.headers}


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    """The API origin is reachable directly, so it needs its own headers.

    nginx sets these for the SPA it serves, but the README points a reviewer at
    :8000 as well — and that origin previously had none of them while a comment
    in nginx.conf claimed the API set its own.
    """
    headers = client.get("/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in headers


def test_docs_are_exempt_from_the_restrictive_csp(client: TestClient) -> None:
    """Swagger UI loads its assets from a CDN.

    Applying default-src 'none' to /docs would serve a blank page, so the docs
    routes are excluded deliberately rather than by oversight.
    """
    assert "content-security-policy" not in client.get("/docs").headers


def test_cors_does_not_allow_credentials(client: TestClient) -> None:
    """Nothing travels in a cookie, so nothing needs credentialed requests.

    Enabling it would widen what a browser sends cross-origin in exchange for
    nothing.
    """
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert "access-control-allow-credentials" not in {
        key.lower() for key in response.headers
    }
