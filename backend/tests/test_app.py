"""App wiring: health probe, router mounting, and CORS allow-list.

Docker healthchecks depend on /health, and the compose file gates the
backend on it — so these assertions protect the startup contract.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def test_documented_endpoints_exist(client: TestClient) -> None:
    """Every path the README publishes must be in the served schema.

    This replaces two tests that asserted constants against themselves —
    `API_V1_PREFIX == "/api/v1"` and each router's prefix against its own
    literal. Those could not fail: changing the constant changed both sides.
    Comparing the live schema against the documented contract can, and catches
    the drift that actually happens when an endpoint is renamed but the README
    is not.
    """
    served = set(client.get("/openapi.json").json()["paths"])

    readme = (Path(__file__).resolve().parent.parent.parent / "README.md").read_text(
        encoding="utf-8"
    )

    # Paths as the README writes them, e.g. `/api/v1/jobs/{id}`.
    documented = set(re.findall(r"`(/api/v1/[^`]+|/health)`", readme))

    # The README uses {id}; FastAPI names the parameter. Compare on shape.
    def shape(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    # Guard against a vacuous pass: an empty set difference is empty. If the
    # regex stops matching, this must fail loudly rather than go green having
    # compared nothing.
    # Guards a vacuous pass: an empty set difference is empty, so a matcher
    # that stopped working would go green having compared nothing. Set below
    # the real count (19) but far above zero.
    assert len(documented) >= 15, (
        f"only parsed {len(documented)} paths from the README — the matcher "
        "has probably stopped working"
    )

    missing = {
        path
        for path in documented
        if shape(path) not in {shape(served_path) for served_path in served}
    }

    assert not missing, f"documented but not served: {sorted(missing)}"


def test_every_served_endpoint_is_documented(client: TestClient) -> None:
    """The other direction: an endpoint the README never mentions.

    A route that exists but is undocumented is how DELETE /notifications/{id}
    shipped unlisted for several commits.
    """
    served = set(client.get("/openapi.json").json()["paths"])

    readme = (Path(__file__).resolve().parent.parent.parent / "README.md").read_text(
        encoding="utf-8"
    )

    def shape(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    documented = {
        shape(path) for path in re.findall(r"`(/api/v1/[^`]+|/health)`", readme)
    }

    # Guards a vacuous pass: an empty set difference is empty, so a matcher
    # that stopped working would go green having compared nothing. Set below
    # the real count (19) but far above zero.
    assert len(documented) >= 15, (
        f"only parsed {len(documented)} paths from the README — the matcher "
        "has probably stopped working"
    )

    undocumented = {
        path
        for path in served
        if shape(path) not in documented and not path.startswith("/openapi")
    }

    assert not undocumented, f"served but not documented: {sorted(undocumented)}"


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
