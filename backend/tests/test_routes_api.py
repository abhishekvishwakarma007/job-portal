"""HTTP-level coverage for the routes their services left untested.

The services behind profile, notifications, messaging, recommendations, and
token refresh are well covered. What was not covered is the wiring: whether the
right role gate is attached, whether the right status code comes back, and
whether a caller who should not reach an endpoint actually cannot.

A service can be perfectly correct behind a route that forgot its gate.
"""

import uuid
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
    """The HR account owning the posting."""
    return make_user(db_session, "hr@test.com", UserRole.HR)


@pytest.fixture
def other_hr_user(db_session: Session) -> User:
    """A second HR account, for cross-tenant checks."""
    return make_user(db_session, "hr2@test.com", UserRole.HR)


@pytest.fixture
def candidate(db_session: Session) -> User:
    """The applying candidate."""
    return make_user(db_session, "candidate@test.com", UserRole.CANDIDATE)


@pytest.fixture
def job(db_session: Session, hr_user: User) -> Job:
    """A published posting owned by hr_user."""
    posting = Job(
        title="Senior Platform Engineer",
        company="Northwind Labs",
        description="Own the deployment pipeline using Docker and Postgres.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        created_by_id=hr_user.id,
    )
    db_session.add(posting)
    db_session.commit()
    db_session.refresh(posting)
    return posting


def auth(user: User) -> dict[str, str]:
    """Authorization header for the given user."""
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def apply_to(client: TestClient, job: Job, user: User) -> Any:
    """Submit an application and return the created body."""
    return client.post(
        f"{API_V1_PREFIX}/applications",
        json={"job_id": str(job.id), "cover_letter": "Docker and Postgres daily."},
        headers=auth(user),
    ).json()


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


def test_candidate_reads_their_profile(client: TestClient, candidate: User) -> None:
    """Created on first read, so the first GET is a 200 rather than a 404."""
    response = client.get(f"{API_V1_PREFIX}/profile/me", headers=auth(candidate))

    assert response.status_code == 200
    assert response.json()["user_id"] == str(candidate.id)


def test_candidate_updates_their_profile(client: TestClient, candidate: User) -> None:
    """The PATCH round-trips and normalises."""
    response = client.patch(
        f"{API_V1_PREFIX}/profile/me",
        json={"key_skills": " Python ,, Docker "},
        headers=auth(candidate),
    )

    assert response.status_code == 200
    assert response.json()["key_skills"] == "Python, Docker"


def test_hr_cannot_reach_the_profile_endpoints(client: TestClient, hr_user: User) -> None:
    """Profiles are a candidate feature; the gate must be on both verbs."""
    assert (
        client.get(f"{API_V1_PREFIX}/profile/me", headers=auth(hr_user)).status_code
        == 403
    )
    assert (
        client.patch(
            f"{API_V1_PREFIX}/profile/me",
            json={"headline": "x"},
            headers=auth(hr_user),
        ).status_code
        == 403
    )


def test_anonymous_cannot_reach_the_profile(client: TestClient) -> None:
    """No token, no profile."""
    assert client.get(f"{API_V1_PREFIX}/profile/me").status_code == 401


def test_profile_rejects_an_over_long_field(client: TestClient, candidate: User) -> None:
    """Validation runs at the boundary, not only in the browser."""
    response = client.patch(
        f"{API_V1_PREFIX}/profile/me",
        json={"headline": "x" * 500},
        headers=auth(candidate),
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------


def test_owner_gets_a_ranked_shortlist(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """The endpoint returns scored applicants and names its method."""
    apply_to(client, job, candidate)

    response = client.get(
        f"{API_V1_PREFIX}/jobs/{job.id}/recommendations", headers=auth(hr_user)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "keyword-overlap"
    assert body["items"][0]["score"] > 0


def test_candidate_cannot_read_a_shortlist(
    client: TestClient, job: Job, candidate: User
) -> None:
    """The gate the reviewer found unverified.

    A candidate seeing how they rank against other applicants — and who those
    applicants are — would be a straightforward disclosure.
    """
    response = client.get(
        f"{API_V1_PREFIX}/jobs/{job.id}/recommendations", headers=auth(candidate)
    )

    assert response.status_code == 403


def test_other_hr_cannot_read_a_shortlist(
    client: TestClient, job: Job, other_hr_user: User
) -> None:
    """404 rather than 403: a 403 confirms the posting exists."""
    response = client.get(
        f"{API_V1_PREFIX}/jobs/{job.id}/recommendations", headers=auth(other_hr_user)
    )

    assert response.status_code == 404


def test_shortlist_respects_its_limit(
    client: TestClient, job: Job, hr_user: User, db_session: Session
) -> None:
    """A shortlist that returns everyone is not a shortlist."""
    for index in range(3):
        applicant = make_user(db_session, f"c{index}@test.com", UserRole.CANDIDATE)
        apply_to(client, job, applicant)

    response = client.get(
        f"{API_V1_PREFIX}/jobs/{job.id}/recommendations",
        params={"limit": 2},
        headers=auth(hr_user),
    )

    assert len(response.json()["items"]) == 2


# --------------------------------------------------------------------------
# Contacting an applicant
# --------------------------------------------------------------------------


def test_owner_can_message_an_applicant(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """Happy path: the message becomes a notification for the applicant."""
    application = apply_to(client, job, candidate)

    response = client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "We would like to invite you to a first interview."},
        headers=auth(hr_user),
    )

    assert response.status_code == 201
    assert "first interview" in response.json()["body"]


def test_candidate_cannot_message_an_applicant(
    client: TestClient, job: Job, candidate: User
) -> None:
    """Messaging is an HR capability."""
    application = apply_to(client, job, candidate)

    response = client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Hello."},
        headers=auth(candidate),
    )

    assert response.status_code == 403


def test_other_hr_cannot_message_someone_elses_applicant(
    client: TestClient, job: Job, candidate: User, other_hr_user: User
) -> None:
    """Only the posting's owner may write to its applicants."""
    application = apply_to(client, job, candidate)

    response = client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Hello."},
        headers=auth(other_hr_user),
    )

    assert response.status_code == 404


def test_message_cannot_be_empty(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """An empty invite helps nobody."""
    application = apply_to(client, job, candidate)

    response = client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": ""},
        headers=auth(hr_user),
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def test_recipient_lists_and_reads_their_notifications(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """List, unread count, and mark-read over HTTP."""
    application = apply_to(client, job, candidate)
    client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Interview invitation."},
        headers=auth(hr_user),
    )

    listed = client.get(f"{API_V1_PREFIX}/notifications/mine", headers=auth(candidate))
    assert listed.status_code == 200
    assert listed.json()["unread"] == 1

    notification_id = listed.json()["items"][0]["id"]
    marked = client.patch(
        f"{API_V1_PREFIX}/notifications/{notification_id}/read",
        headers=auth(candidate),
    )

    assert marked.status_code == 200
    assert marked.json()["is_read"] is True


def test_cannot_read_another_users_notification(
    client: TestClient, job: Job, candidate: User, hr_user: User, db_session: Session
) -> None:
    """404, not 403 — whether an id exists is not another user's business."""
    application = apply_to(client, job, candidate)
    client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Hello."},
        headers=auth(hr_user),
    )
    notification_id = client.get(
        f"{API_V1_PREFIX}/notifications/mine", headers=auth(candidate)
    ).json()["items"][0]["id"]

    stranger = make_user(db_session, "stranger@test.com", UserRole.CANDIDATE)

    assert (
        client.patch(
            f"{API_V1_PREFIX}/notifications/{notification_id}/read",
            headers=auth(stranger),
        ).status_code
        == 404
    )


def test_dismissing_a_notification(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """Dismiss removes it from the inbox."""
    application = apply_to(client, job, candidate)
    client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Hello."},
        headers=auth(hr_user),
    )
    notification_id = client.get(
        f"{API_V1_PREFIX}/notifications/mine", headers=auth(candidate)
    ).json()["items"][0]["id"]

    removed = client.delete(
        f"{API_V1_PREFIX}/notifications/{notification_id}", headers=auth(candidate)
    )

    assert removed.status_code == 204
    assert (
        client.get(f"{API_V1_PREFIX}/notifications/mine", headers=auth(candidate)).json()[
            "total"
        ]
        == 0
    )


def test_cannot_dismiss_another_users_notification(
    client: TestClient, job: Job, candidate: User, hr_user: User, db_session: Session
) -> None:
    """Otherwise anyone holding an id could clear someone else's inbox."""
    application = apply_to(client, job, candidate)
    client.post(
        f"{API_V1_PREFIX}/applications/{application['id']}/contact",
        json={"message": "Hello."},
        headers=auth(hr_user),
    )
    notification_id = client.get(
        f"{API_V1_PREFIX}/notifications/mine", headers=auth(candidate)
    ).json()["items"][0]["id"]

    stranger = make_user(db_session, "stranger@test.com", UserRole.CANDIDATE)

    assert (
        client.delete(
            f"{API_V1_PREFIX}/notifications/{notification_id}",
            headers=auth(stranger),
        ).status_code
        == 404
    )


def test_anonymous_cannot_list_notifications(client: TestClient) -> None:
    """An inbox is not public."""
    assert client.get(f"{API_V1_PREFIX}/notifications/mine").status_code == 401


# --------------------------------------------------------------------------
# Refresh and logout
# --------------------------------------------------------------------------


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    """Log in and return the token pair."""
    tokens: dict[str, str] = client.post(
        f"{API_V1_PREFIX}/auth/login",
        json={"email": email, "password": PASSWORD},
    ).json()
    return tokens


def test_login_returns_both_tokens(client: TestClient, candidate: User) -> None:
    """The refresh token is issued alongside the access token."""
    tokens = sign_in(client, "candidate@test.com")

    assert tokens["access_token"]
    assert tokens["refresh_token"]


def test_refresh_exchanges_for_a_new_pair(client: TestClient, candidate: User) -> None:
    """Happy path, and the returned refresh token is a different one."""
    tokens = sign_in(client, "candidate@test.com")

    response = client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["refresh_token"] != tokens["refresh_token"]


def test_a_spent_refresh_token_is_refused(client: TestClient, candidate: User) -> None:
    """Rotation-on-use, from the caller's side."""
    tokens = sign_in(client, "candidate@test.com")
    client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    replayed = client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert replayed.status_code == 401


def test_replaying_a_spent_token_kills_the_family(
    client: TestClient, candidate: User
) -> None:
    """The theft response, over HTTP.

    A well-behaved client never replays, so a replay means two parties hold
    tokens from one chain — and the live one dies with the stolen one.
    """
    tokens = sign_in(client, "candidate@test.com")
    rotated = client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    ).json()

    client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    still_live = client.post(
        f"{API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": rotated["refresh_token"]},
    )

    assert still_live.status_code == 401


def test_an_unknown_refresh_token_is_refused(client: TestClient) -> None:
    """A value that was never issued must not mint an access token."""
    response = client.post(
        f"{API_V1_PREFIX}/auth/refresh", json={"refresh_token": "never-issued"}
    )

    assert response.status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient, candidate: User) -> None:
    """Logout actually ends the session."""
    tokens = sign_in(client, "candidate@test.com")

    assert (
        client.post(
            f"{API_V1_PREFIX}/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"{API_V1_PREFIX}/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code
        == 401
    )


def test_logout_is_silent_for_an_unknown_token(client: TestClient) -> None:
    """204 either way.

    Logging out should succeed regardless, and a different answer would confirm
    which tokens were ever real to anyone able to call it.
    """
    response = client.post(
        f"{API_V1_PREFIX}/auth/logout", json={"refresh_token": str(uuid.uuid4())}
    )

    assert response.status_code == 204
