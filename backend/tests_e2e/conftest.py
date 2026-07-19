"""Fixtures for the end-to-end suite.

These tests talk to a running stack over HTTP — no TestClient, no dependency
overrides, no in-process shortcuts. They exercise nginx, the proxy, uvicorn,
the real database, and the migrations that built it, which is the combination
every other test deliberately avoids.

Run separately from the unit suite (`pytest tests_e2e`), because they need
`docker compose up` first. pyproject's testpaths points at `tests`, so a plain
`pytest` never picks these up by accident.
"""

import os
import time
import uuid
from collections.abc import Iterator

import httpx
import pytest

# Through the frontend's nginx by default: that is the path a browser takes,
# so it covers the proxy as well as the API. Override to hit the backend
# directly when debugging which of the two broke.
DEFAULT_BASE_URL = "http://localhost:5173"

# The credentials the README publishes. Using them rather than registering new
# accounts keeps the suite off the registration rate limit, and doubles as a
# check that the documented logins still work.
HR_CREDENTIALS = {"email": "admin@test.com", "password": "Admin@1234"}
CANDIDATE_CREDENTIALS = {"email": "user@test.com", "password": "User@1234"}

STARTUP_TIMEOUT_SECONDS = 60


@pytest.fixture(scope="session")
def base_url() -> str:
    """Where the running stack is."""
    return os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api_url(base_url: str) -> str:
    """The versioned API root."""
    return f"{base_url}/api/v1"


@pytest.fixture(scope="session", autouse=True)
def _wait_for_stack(base_url: str) -> None:
    """Fail with a useful message when the stack is not up.

    Without this the first test fails on a connection error, which reads as a
    broken application rather than "you forgot to start it".
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/api/v1/jobs", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(2)

    pytest.fail(
        f"No stack reachable at {base_url} after {STARTUP_TIMEOUT_SECONDS}s. "
        "Start it with: docker compose up -d --build"
    )


@pytest.fixture(scope="session")
def client(base_url: str) -> Iterator[httpx.Client]:
    """A plain HTTP client. No auth — each test supplies its own."""
    with httpx.Client(base_url=base_url, timeout=15) as http_client:
        yield http_client


def _token(client: httpx.Client, credentials: dict[str, str]) -> str:
    """Sign in and return the access token."""
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200, (
        f"Could not sign in as {credentials['email']}: "
        f"{response.status_code} {response.text}"
    )
    return str(response.json()["access_token"])


@pytest.fixture(scope="session")
def hr_headers(client: httpx.Client) -> dict[str, str]:
    """Authorization header for the seeded HR account."""
    return {"Authorization": f"Bearer {_token(client, HR_CREDENTIALS)}"}


@pytest.fixture(scope="session")
def candidate_headers(client: httpx.Client) -> dict[str, str]:
    """Authorization header for the seeded candidate account."""
    return {"Authorization": f"Bearer {_token(client, CANDIDATE_CREDENTIALS)}"}


@pytest.fixture
def posted_job(
    client: httpx.Client, hr_headers: dict[str, str]
) -> Iterator[dict[str, object]]:
    """A freshly posted job, removed afterwards.

    Created per test with a unique title rather than reusing a seeded posting:
    these run against a persistent database, so a test that mutated shared data
    would pass once and then fail on every rerun. Deleting it cascades to any
    applications, leaving the stack as it was found.
    """
    title = f"E2E Platform Engineer {uuid.uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/jobs",
        headers=hr_headers,
        json={
            "title": title,
            "company": "Northwind Labs",
            "description": (
                "Own the deployment pipeline end to end, working across "
                "Docker and Postgres tooling."
            ),
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "is_published": True,
        },
    )
    assert response.status_code == 201, response.text
    job = response.json()

    yield job

    client.delete(f"/api/v1/jobs/{job['id']}", headers=hr_headers)
