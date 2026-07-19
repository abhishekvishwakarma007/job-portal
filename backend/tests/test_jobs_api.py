"""Job posting endpoints and their authorisation boundaries.

The interesting assertions here are about who may do what. A candidate reaching
a management endpoint, or an HR user reaching another HR user's posting, are
the failures that matter — a working create is the easy part.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.job import EmploymentType, Job
from app.models.user import User, UserRole
from app.services.auth import register_user

JOBS_URL = f"{API_V1_PREFIX}/jobs"

PASSWORD = "Str0ng@Password"


@pytest.fixture
def client(valid_env: None, db_session: Session) -> Iterator[TestClient]:
    """A TestClient sharing the test's session."""
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user(db: Session, email: str, role: UserRole) -> User:
    """Create a persisted user of the given role."""
    return register_user(
        db, email=email, password=PASSWORD, full_name="Test Person", role=role
    )


@pytest.fixture
def hr_user(db_session: Session) -> User:
    """The HR account that owns postings in most tests."""
    return make_user(db_session, "hr@test.com", UserRole.HR)


@pytest.fixture
def other_hr_user(db_session: Session) -> User:
    """A second HR account, used to prove postings are not shared."""
    return make_user(db_session, "hr2@test.com", UserRole.HR)


@pytest.fixture
def candidate_user(db_session: Session) -> User:
    """A candidate account, used to prove the role gates hold."""
    return make_user(db_session, "candidate@test.com", UserRole.CANDIDATE)


def auth(user: User) -> dict[str, str]:
    """Authorization header for the given user."""
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def job_payload(**overrides: Any) -> dict[str, Any]:
    """A valid job body, overridable per test."""
    payload: dict[str, Any] = {
        "title": "Senior Platform Engineer",
        "company": "Northwind Labs",
        "description": "Own the deployment pipeline end to end.",
        "location": "Remote",
        "employment_type": EmploymentType.FULL_TIME.value,
    }
    payload.update(overrides)
    return payload


def create_job(db: Session, owner: User, **overrides: Any) -> Job:
    """Persist a job owned by the given user."""
    fields = job_payload(**overrides)
    job = Job(
        title=fields["title"],
        company=fields["company"],
        description=fields["description"],
        location=fields["location"],
        employment_type=EmploymentType(fields["employment_type"]),
        is_published=overrides.get("is_published", True),
        created_by_id=owner.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------------------
# Creating
# --------------------------------------------------------------------------


def test_hr_can_create_a_job(client: TestClient, hr_user: User) -> None:
    """Happy path: an HR user posts a role."""
    response = client.post(JOBS_URL, json=job_payload(), headers=auth(hr_user))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Senior Platform Engineer"
    assert body["created_by"]["id"] == str(hr_user.id)


def test_created_job_is_owned_by_the_caller(
    client: TestClient, hr_user: User, other_hr_user: User, db_session: Session
) -> None:
    """Ownership comes from the token, never from the request body.

    Accepting a created_by_id from the client would let one HR user post jobs
    in another's name.
    """
    client.post(
        JOBS_URL,
        json=job_payload(created_by_id=str(other_hr_user.id)),
        headers=auth(hr_user),
    )

    job = db_session.query(Job).one()
    assert job.created_by_id == hr_user.id


def test_candidate_cannot_create_a_job(client: TestClient, candidate_user: User) -> None:
    """The role gate: posting jobs is an HR capability."""
    response = client.post(JOBS_URL, json=job_payload(), headers=auth(candidate_user))

    assert response.status_code == 403


def test_anonymous_cannot_create_a_job(client: TestClient) -> None:
    """No token, no posting."""
    assert client.post(JOBS_URL, json=job_payload()).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""},
        {"description": ""},
        {"location": ""},
        {"employment_type": "PERMANENT_VACATION"},
        {"title": "x" * 201},
    ],
)
def test_create_rejects_invalid_input(
    client: TestClient, hr_user: User, overrides: dict[str, Any]
) -> None:
    """Validation runs server-side regardless of what the browser allowed."""
    response = client.post(JOBS_URL, json=job_payload(**overrides), headers=auth(hr_user))

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Browsing
# --------------------------------------------------------------------------


def test_anyone_can_list_published_jobs(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Browsing is public — candidates must see roles before signing up."""
    create_job(db_session, hr_user)

    response = client.get(JOBS_URL)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_listing_excludes_unpublished_jobs(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """A draft must not appear in the public list."""
    create_job(db_session, hr_user, is_published=False)

    assert client.get(JOBS_URL).json()["items"] == []


def test_listing_is_newest_first(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Order is part of the contract the UI renders against."""
    create_job(db_session, hr_user, title="Older")
    create_job(db_session, hr_user, title="Newer")

    titles = [item["title"] for item in client.get(JOBS_URL).json()["items"]]

    assert titles == ["Newer", "Older"]


def test_listing_can_be_searched_by_title(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Search is case-insensitive and matches partial titles."""
    create_job(db_session, hr_user, title="Backend Engineer")
    create_job(db_session, hr_user, title="Designer")

    items = client.get(JOBS_URL, params={"search": "engineer"}).json()["items"]

    assert [item["title"] for item in items] == ["Backend Engineer"]


def test_listing_is_paginated(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """An unbounded list is a denial-of-service waiting to happen."""
    for index in range(3):
        create_job(db_session, hr_user, title=f"Role {index}")

    body = client.get(JOBS_URL, params={"limit": 2}).json()

    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_anyone_can_read_a_published_job(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Detail pages are public for published roles."""
    job = create_job(db_session, hr_user)

    assert client.get(f"{JOBS_URL}/{job.id}").status_code == 200


def test_unpublished_job_is_not_readable_by_a_candidate(
    client: TestClient, hr_user: User, candidate_user: User, db_session: Session
) -> None:
    """A draft is invisible, not merely unapplicable.

    404 rather than 403: a 403 would confirm the posting exists, which is
    exactly what an unpublished draft should not reveal.
    """
    job = create_job(db_session, hr_user, is_published=False)

    response = client.get(f"{JOBS_URL}/{job.id}", headers=auth(candidate_user))

    assert response.status_code == 404


def test_owner_can_read_their_own_unpublished_job(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """The author still needs to see their draft to finish it."""
    job = create_job(db_session, hr_user, is_published=False)

    response = client.get(f"{JOBS_URL}/{job.id}", headers=auth(hr_user))

    assert response.status_code == 200


def test_unknown_job_id_is_a_404(client: TestClient) -> None:
    """A well-formed but absent id must not 500."""
    missing = "00000000-0000-0000-0000-000000000001"

    assert client.get(f"{JOBS_URL}/{missing}").status_code == 404


def test_malformed_job_id_is_rejected(client: TestClient) -> None:
    """A non-UUID path segment is a validation error, not a lookup."""
    assert client.get(f"{JOBS_URL}/not-a-uuid").status_code == 422


# --------------------------------------------------------------------------
# Updating and deleting
# --------------------------------------------------------------------------


def test_owner_can_update_their_job(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Happy path for editing."""
    job = create_job(db_session, hr_user)

    response = client.patch(
        f"{JOBS_URL}/{job.id}", json={"title": "Staff Engineer"}, headers=auth(hr_user)
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Staff Engineer"


def test_partial_update_leaves_other_fields_alone(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """PATCH must not blank out fields the caller did not mention."""
    job = create_job(db_session, hr_user)
    original_description = job.description

    client.patch(
        f"{JOBS_URL}/{job.id}", json={"title": "Staff Engineer"}, headers=auth(hr_user)
    )

    db_session.refresh(job)
    assert job.description == original_description


def test_other_hr_user_cannot_update_the_job(
    client: TestClient, hr_user: User, other_hr_user: User, db_session: Session
) -> None:
    """Cross-tenant write must fail, and must not confirm the row exists.

    404 rather than 403 for the same reason as reads: distinguishing "exists
    but forbidden" from "does not exist" leaks the id space of other accounts.
    """
    job = create_job(db_session, hr_user)

    response = client.patch(
        f"{JOBS_URL}/{job.id}", json={"title": "Hijacked"}, headers=auth(other_hr_user)
    )

    assert response.status_code == 404


def test_candidate_cannot_update_a_job(
    client: TestClient, hr_user: User, candidate_user: User, db_session: Session
) -> None:
    """The role gate applies to edits, not only to creation."""
    job = create_job(db_session, hr_user)

    response = client.patch(
        f"{JOBS_URL}/{job.id}", json={"title": "Hijacked"}, headers=auth(candidate_user)
    )

    assert response.status_code == 403


def test_owner_can_delete_their_job(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Happy path for removal."""
    job = create_job(db_session, hr_user)

    response = client.delete(f"{JOBS_URL}/{job.id}", headers=auth(hr_user))

    assert response.status_code == 204
    assert db_session.query(Job).count() == 0


def test_other_hr_user_cannot_delete_the_job(
    client: TestClient, hr_user: User, other_hr_user: User, db_session: Session
) -> None:
    """Cross-tenant delete must fail and leave the row intact."""
    job = create_job(db_session, hr_user)

    response = client.delete(f"{JOBS_URL}/{job.id}", headers=auth(other_hr_user))

    assert response.status_code == 404
    assert db_session.query(Job).count() == 1


def test_owner_can_unpublish_a_job(
    client: TestClient, hr_user: User, db_session: Session
) -> None:
    """Unpublishing removes a role from the public list without deleting it."""
    job = create_job(db_session, hr_user)

    client.patch(
        f"{JOBS_URL}/{job.id}", json={"is_published": False}, headers=auth(hr_user)
    )

    assert client.get(JOBS_URL).json()["items"] == []


def test_hr_can_list_their_own_jobs_including_drafts(
    client: TestClient, hr_user: User, other_hr_user: User, db_session: Session
) -> None:
    """The management view shows an author their drafts and nobody else's."""
    create_job(db_session, hr_user, title="Mine published")
    create_job(db_session, hr_user, title="Mine draft", is_published=False)
    create_job(db_session, other_hr_user, title="Theirs")

    body = client.get(f"{JOBS_URL}/mine", headers=auth(hr_user)).json()

    assert {item["title"] for item in body["items"]} == {"Mine published", "Mine draft"}


def test_candidate_cannot_list_managed_jobs(
    client: TestClient, candidate_user: User
) -> None:
    """The management view is HR-only."""
    response = client.get(f"{JOBS_URL}/mine", headers=auth(candidate_user))

    assert response.status_code == 403
