"""End-to-end smoke tests against a running stack.

Everything here goes over HTTP through nginx, so a pass means the containers,
the proxy, the migrations, and the seed all did their jobs — not merely that
the Python functions agree with each other.

The scenarios follow the journey the README describes, because that is what an
assessor will actually do: sign in, post a role, apply, get refused a second
time, move the application along, and receive a message about it.
"""

import uuid
from typing import Any

import httpx
import pytest


def _post_application(
    client: httpx.Client, job_id: str, headers: dict[str, str], letter: str
) -> httpx.Response:
    """Submit an application."""
    return client.post(
        "/api/v1/applications",
        headers=headers,
        json={"job_id": job_id, "cover_letter": letter},
    )


# --------------------------------------------------------------------------
# The stack is actually serving
# --------------------------------------------------------------------------


def test_ui_is_served(client: httpx.Client) -> None:
    """The SPA loads at the documented port."""
    response = client.get("/")

    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_client_routes_fall_back_to_the_spa(client: httpx.Client) -> None:
    """A deep link has no file on disk; nginx must serve index.html anyway."""
    response = client.get("/jobs")

    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_api_is_reachable_through_the_proxy(client: httpx.Client) -> None:
    """The browser talks to one origin; nginx forwards /api to the backend."""
    response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert "items" in response.json()


def test_api_404_is_json_not_html(client: httpx.Client) -> None:
    """The SPA fallback must not swallow API 404s.

    If /api were matched by the catch-all, a missing endpoint would return the
    HTML shell and every client error handler would break on the parse.
    """
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_security_headers_are_present(client: httpx.Client) -> None:
    """The headers nginx is configured to set actually reach the browser."""
    headers = client.get("/").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in headers


# --------------------------------------------------------------------------
# The documented credentials work
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "password", "expected_role"),
    [
        ("admin@test.com", "Admin@1234", "HR"),
        ("user@test.com", "User@1234", "CANDIDATE"),
    ],
)
def test_readme_credentials_sign_in(
    client: httpx.Client, email: str, password: str, expected_role: str
) -> None:
    """Both published logins work and resolve to the documented role.

    This is the check that would have caught the seeded accounts created at a
    reserved TLD, which existed in the database but were refused at the API.
    """
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["role"] == expected_role


def test_login_does_not_reveal_whether_an_account_exists(
    client: httpx.Client,
) -> None:
    """Wrong password and unknown address must be indistinguishable."""
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Wr0ng@Password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"nobody-{uuid.uuid4().hex}@test.com",
            "password": "Wr0ng@Password",
        },
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# --------------------------------------------------------------------------
# The journey the README describes
# --------------------------------------------------------------------------


def test_posted_job_appears_in_public_browse(
    client: httpx.Client, posted_job: dict[str, Any]
) -> None:
    """An HR user posts a role and an anonymous visitor can find it."""
    response = client.get("/api/v1/jobs", params={"search": posted_job["title"]})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [posted_job["id"]]


def test_filters_narrow_the_browse_list(
    client: httpx.Client, posted_job: dict[str, Any]
) -> None:
    """Company, location, and type filters all reach the database."""
    matching = client.get(
        "/api/v1/jobs",
        params={
            "search": posted_job["title"],
            "company": "northwind",
            "location": "remote",
            "employment_type": "FULL_TIME",
        },
    )
    non_matching = client.get(
        "/api/v1/jobs",
        params={"search": posted_job["title"], "employment_type": "INTERNSHIP"},
    )

    assert matching.json()["total"] == 1
    assert non_matching.json()["total"] == 0


def test_candidate_applies_and_cannot_apply_twice(
    client: httpx.Client,
    posted_job: dict[str, Any],
    candidate_headers: dict[str, str],
) -> None:
    """The duplicate-apply guard, end to end.

    The constraint lives in the schema, so this proves the migration that
    created it actually ran against the container's database.
    """
    first = _post_application(
        client, posted_job["id"], candidate_headers, "Six years of pipeline work."
    )
    second = _post_application(
        client, posted_job["id"], candidate_headers, "Applying twice by mistake."
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409


def test_hr_reviews_and_advances_an_application(
    client: httpx.Client,
    posted_job: dict[str, Any],
    candidate_headers: dict[str, str],
    hr_headers: dict[str, str],
) -> None:
    """HR sees the applicant, moves them along, and the candidate sees it."""
    _post_application(
        client, posted_job["id"], candidate_headers, "Docker and Postgres daily."
    )

    pipeline = client.get(
        f"/api/v1/jobs/{posted_job['id']}/applications", headers=hr_headers
    )
    assert pipeline.status_code == 200
    assert pipeline.json()["total"] == 1

    application_id = pipeline.json()["items"][0]["id"]
    updated = client.patch(
        f"/api/v1/applications/{application_id}",
        headers=hr_headers,
        json={"status": "ACCEPTED"},
    )
    assert updated.status_code == 200

    mine = client.get("/api/v1/applications/mine", headers=candidate_headers)
    statuses = {item["job"]["id"]: item["status"] for item in mine.json()["items"]}
    assert statuses[posted_job["id"]] == "ACCEPTED"


def test_hr_shortlist_ranks_the_applicant(
    client: httpx.Client,
    posted_job: dict[str, Any],
    candidate_headers: dict[str, str],
    hr_headers: dict[str, str],
) -> None:
    """The recommendation endpoint returns a labelled, scored shortlist."""
    _post_application(
        client,
        posted_job["id"],
        candidate_headers,
        "I own deployment pipeline work across Docker and Postgres.",
    )

    response = client.get(
        f"/api/v1/jobs/{posted_job['id']}/recommendations", headers=hr_headers
    )

    assert response.status_code == 200
    body = response.json()
    # Named in the payload so no client can present the score as an assessment.
    assert body["method"] == "keyword-overlap"
    assert body["items"][0]["score"] > 0


def test_hr_message_reaches_the_candidate_as_an_invite(
    client: httpx.Client,
    posted_job: dict[str, Any],
    candidate_headers: dict[str, str],
    hr_headers: dict[str, str],
) -> None:
    """Contacting an applicant lands in their invites. No mail is sent."""
    _post_application(client, posted_job["id"], candidate_headers, "Keen to talk.")
    pipeline = client.get(
        f"/api/v1/jobs/{posted_job['id']}/applications", headers=hr_headers
    )
    application_id = pipeline.json()["items"][0]["id"]

    marker = uuid.uuid4().hex[:8]
    sent = client.post(
        f"/api/v1/applications/{application_id}/contact",
        headers=hr_headers,
        json={"message": f"Interview invitation {marker}"},
    )
    assert sent.status_code == 201, sent.text

    inbox = client.get("/api/v1/notifications/mine", headers=candidate_headers)
    assert inbox.status_code == 200

    delivered = [item for item in inbox.json()["items"] if marker in item["body"]]
    assert delivered, "the message did not reach the candidate's invites"

    # Dismiss it. Deleting the job only nulls the notification's job_id, so
    # without this the suite leaves an orphan invite in the demo database
    # naming a throwaway test posting — which is exactly what it did before
    # this cleanup existed.
    for item in delivered:
        client.delete(f"/api/v1/notifications/{item['id']}", headers=candidate_headers)


def test_candidate_profile_round_trips(
    client: httpx.Client, candidate_headers: dict[str, str]
) -> None:
    """A profile saves and normalises its skill list."""
    response = client.patch(
        "/api/v1/profile/me",
        headers=candidate_headers,
        json={"key_skills": " Python ,, FastAPI ,Postgres "},
    )

    assert response.status_code == 200
    assert response.json()["key_skills"] == "Python, FastAPI, Postgres"


# --------------------------------------------------------------------------
# Authorisation holds over the wire
# --------------------------------------------------------------------------


def test_candidate_cannot_post_a_job(
    client: httpx.Client, candidate_headers: dict[str, str]
) -> None:
    """The role gate answers 403 — the endpoint's existence is not a secret."""
    response = client.post(
        "/api/v1/jobs",
        headers=candidate_headers,
        json={
            "title": "Should not exist",
            "company": "Nowhere",
            "description": "x",
            "location": "y",
            "employment_type": "FULL_TIME",
        },
    )

    assert response.status_code == 403


def test_anonymous_cannot_reach_a_protected_endpoint(
    client: httpx.Client,
) -> None:
    """No token, no access."""
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/jobs/mine").status_code == 401


def test_hr_cannot_read_a_candidate_endpoint(
    client: httpx.Client, hr_headers: dict[str, str]
) -> None:
    """Role gates cut both ways."""
    assert client.get("/api/v1/applications/mine", headers=hr_headers).status_code == 403


def test_unpublished_job_is_hidden_from_candidates(
    client: httpx.Client,
    hr_headers: dict[str, str],
    candidate_headers: dict[str, str],
) -> None:
    """A draft is 404 to everyone but its author, never 403.

    403 would confirm the posting exists, which is exactly what a draft must
    not reveal.
    """
    created = client.post(
        "/api/v1/jobs",
        headers=hr_headers,
        json={
            "title": f"E2E Draft {uuid.uuid4().hex[:8]}",
            "company": "Northwind Labs",
            "description": "Not advertised.",
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "is_published": False,
        },
    )
    job_id = created.json()["id"]

    try:
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
        assert (
            client.get(f"/api/v1/jobs/{job_id}", headers=candidate_headers).status_code
            == 404
        )
        # The author still sees their own draft.
        assert client.get(f"/api/v1/jobs/{job_id}", headers=hr_headers).status_code == 200
    finally:
        client.delete(f"/api/v1/jobs/{job_id}", headers=hr_headers)


def test_a_new_account_can_register_and_sign_in(client: httpx.Client) -> None:
    """The one step of the documented journey the suite used to skip.

    Registration was avoided here to stay clear of the rate limit, which left
    the first step of "register -> login -> apply" unproven end to end. One
    account per run, at a unique address, stays well inside the budget.

    There is no delete-account endpoint, so this leaves a row behind by
    design — the alternative is reaching into the database from a black-box
    suite, which would couple it to the schema it is meant to be independent
    of. The address is namespaced so the residue is obvious for what it is.
    """
    marker = uuid.uuid4().hex[:10]
    credentials = {
        "email": f"e2e-{marker}@test.com",
        "password": "E2ePassw0rd!",
    }

    created = client.post(
        "/api/v1/auth/register",
        json={**credentials, "full_name": "E2E Candidate", "role": "CANDIDATE"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "CANDIDATE"
    # The response must never carry password material back.
    assert "password" not in created.json()

    signed_in = client.post("/api/v1/auth/login", json=credentials)
    assert signed_in.status_code == 200, signed_in.text

    token = signed_in.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == credentials["email"]
