"""Application endpoints and their authorisation boundaries.

Three properties carry the weight here: a candidate cannot apply twice, one
candidate cannot read another's application, and an HR user sees only the
pipelines of jobs they own.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.router import API_V1_PREFIX
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.application import Application, ApplicationStatus
from app.models.job import EmploymentType, Job
from app.models.user import User, UserRole
from app.services.auth import register_user

APPLICATIONS_URL = f"{API_V1_PREFIX}/applications"
JOBS_URL = f"{API_V1_PREFIX}/jobs"

PASSWORD = "Str0ng@Password"
COVER_LETTER = "I have run deployment pipelines for six years."


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
    """The HR account owning the job under test."""
    return make_user(db_session, "hr@test.com", UserRole.HR)


@pytest.fixture
def other_hr_user(db_session: Session) -> User:
    """A second HR account, to prove pipelines are not shared."""
    return make_user(db_session, "hr2@test.com", UserRole.HR)


@pytest.fixture
def candidate(db_session: Session) -> User:
    """The applying candidate."""
    return make_user(db_session, "candidate@test.com", UserRole.CANDIDATE)


@pytest.fixture
def other_candidate(db_session: Session) -> User:
    """A second candidate, to prove applications are private."""
    return make_user(db_session, "candidate2@test.com", UserRole.CANDIDATE)


@pytest.fixture
def job(db_session: Session, hr_user: User) -> Job:
    """A published job owned by hr_user."""
    return make_job(db_session, hr_user)


def make_job(db: Session, owner: User, *, is_published: bool = True) -> Job:
    """Persist a job owned by the given HR user."""
    job = Job(
        title="Senior Platform Engineer",
        description="Own the deployment pipeline end to end.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        is_published=is_published,
        created_by_id=owner.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def auth(user: User) -> dict[str, str]:
    """Authorization header for the given user."""
    return {
        "Authorization": f"Bearer {create_access_token(user_id=user.id, role=user.role)}"
    }


def apply_to(client: TestClient, job: Job, user: User, **overrides: Any) -> Any:
    """Submit an application and return the raw response."""
    payload: dict[str, Any] = {
        "job_id": str(job.id),
        "cover_letter": COVER_LETTER,
    }
    payload.update(overrides)
    return client.post(APPLICATIONS_URL, json=payload, headers=auth(user))


# --------------------------------------------------------------------------
# Applying
# --------------------------------------------------------------------------


def test_candidate_can_apply(client: TestClient, job: Job, candidate: User) -> None:
    """Happy path: a candidate submits an application."""
    response = apply_to(client, job, candidate)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == ApplicationStatus.SUBMITTED.value
    assert body["job"]["id"] == str(job.id)


def test_application_belongs_to_the_caller(
    client: TestClient,
    job: Job,
    candidate: User,
    other_candidate: User,
    db_session: Session,
) -> None:
    """Authorship comes from the token, never the body."""
    apply_to(client, job, candidate, candidate_id=str(other_candidate.id))

    application = db_session.query(Application).one()
    assert application.candidate_id == candidate.id


def test_candidate_cannot_apply_twice(
    client: TestClient, job: Job, candidate: User, db_session: Session
) -> None:
    """The duplicate-apply guard, from the caller's point of view."""
    apply_to(client, job, candidate)

    response = apply_to(client, job, candidate)

    assert response.status_code == 409
    assert db_session.query(Application).count() == 1


def test_duplicate_application_rejected_by_the_database(
    db_session: Session, job: Job, candidate: User
) -> None:
    """The constraint holds even when the service layer is bypassed.

    A service-layer check loses the race between two concurrent submissions:
    both can pass the check before either commits. This asserts the guarantee
    lives in the schema, where a race cannot get around it.
    """
    for _ in range(2):
        db_session.add(
            Application(
                job_id=job.id, candidate_id=candidate.id, cover_letter=COVER_LETTER
            )
        )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_candidates_may_apply_to_one_job(
    client: TestClient, job: Job, candidate: User, other_candidate: User
) -> None:
    """The constraint is per (job, candidate), not per job."""
    apply_to(client, job, candidate)

    assert apply_to(client, job, other_candidate).status_code == 201


def test_one_candidate_may_apply_to_several_jobs(
    client: TestClient, hr_user: User, candidate: User, db_session: Session
) -> None:
    """The constraint must not block a candidate applying elsewhere."""
    first = make_job(db_session, hr_user)
    second = make_job(db_session, hr_user)

    apply_to(client, first, candidate)

    assert apply_to(client, second, candidate).status_code == 201


def test_hr_cannot_apply(client: TestClient, job: Job, hr_user: User) -> None:
    """Applying is a candidate capability."""
    assert apply_to(client, job, hr_user).status_code == 403


def test_anonymous_cannot_apply(client: TestClient, job: Job) -> None:
    """No token, no application."""
    response = client.post(
        APPLICATIONS_URL,
        json={"job_id": str(job.id), "cover_letter": COVER_LETTER},
    )

    assert response.status_code == 401


def test_cannot_apply_to_an_unpublished_job(
    client: TestClient, hr_user: User, candidate: User, db_session: Session
) -> None:
    """A draft is not open for applications, and must not confirm it exists."""
    draft = make_job(db_session, hr_user, is_published=False)

    assert apply_to(client, draft, candidate).status_code == 404


def test_cannot_apply_to_an_unknown_job(client: TestClient, candidate: User) -> None:
    """A well-formed but absent job id is a 404, not a 500."""
    response = client.post(
        APPLICATIONS_URL,
        json={"job_id": str(uuid.uuid4()), "cover_letter": COVER_LETTER},
        headers=auth(candidate),
    )

    assert response.status_code == 404


@pytest.mark.parametrize("cover_letter", ["", "x" * 5001])
def test_apply_rejects_invalid_cover_letter(
    client: TestClient, job: Job, candidate: User, cover_letter: str
) -> None:
    """Validation runs server-side regardless of what the form allowed."""
    assert apply_to(client, job, candidate, cover_letter=cover_letter).status_code == 422


def test_apply_ignores_a_client_supplied_status(
    client: TestClient, job: Job, candidate: User, db_session: Session
) -> None:
    """A candidate must not be able to self-accept.

    Mass-assignment guard: status is server-controlled and absent from the
    create schema, so a body carrying it is ignored rather than honoured.
    """
    apply_to(client, job, candidate, status=ApplicationStatus.ACCEPTED.value)

    application = db_session.query(Application).one()
    assert application.status is ApplicationStatus.SUBMITTED


# --------------------------------------------------------------------------
# Candidate's own applications
# --------------------------------------------------------------------------


def test_candidate_lists_only_their_own_applications(
    client: TestClient, job: Job, candidate: User, other_candidate: User
) -> None:
    """One candidate must never see another's applications."""
    apply_to(client, job, candidate)
    apply_to(client, job, other_candidate)

    body = client.get(f"{APPLICATIONS_URL}/mine", headers=auth(candidate)).json()

    assert body["total"] == 1


def test_candidate_can_read_their_own_application(
    client: TestClient, job: Job, candidate: User
) -> None:
    """The author may read their own submission."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.get(f"{APPLICATIONS_URL}/{application_id}", headers=auth(candidate))

    assert response.status_code == 200


def test_candidate_cannot_read_another_candidates_application(
    client: TestClient, job: Job, candidate: User, other_candidate: User
) -> None:
    """Cross-candidate read must 404 rather than confirm the row exists."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.get(
        f"{APPLICATIONS_URL}/{application_id}", headers=auth(other_candidate)
    )

    assert response.status_code == 404


# --------------------------------------------------------------------------
# HR review
# --------------------------------------------------------------------------


def test_hr_sees_applications_for_their_job(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """The pipeline view for a job the caller owns."""
    apply_to(client, job, candidate)

    body = client.get(f"{JOBS_URL}/{job.id}/applications", headers=auth(hr_user)).json()

    assert body["total"] == 1
    assert body["items"][0]["candidate"]["email"] == "candidate@test.com"


def test_hr_cannot_see_applications_for_another_hr_users_job(
    client: TestClient, job: Job, candidate: User, other_hr_user: User
) -> None:
    """Pipelines are not shared between HR accounts."""
    apply_to(client, job, candidate)

    response = client.get(
        f"{JOBS_URL}/{job.id}/applications", headers=auth(other_hr_user)
    )

    assert response.status_code == 404


def test_candidate_cannot_see_a_job_pipeline(
    client: TestClient, job: Job, candidate: User
) -> None:
    """The pipeline is an HR view."""
    response = client.get(f"{JOBS_URL}/{job.id}/applications", headers=auth(candidate))

    assert response.status_code == 403


def test_hr_can_update_an_application_status(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """Moving an application through the pipeline."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.patch(
        f"{APPLICATIONS_URL}/{application_id}",
        json={"status": ApplicationStatus.UNDER_REVIEW.value},
        headers=auth(hr_user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ApplicationStatus.UNDER_REVIEW.value


def test_hr_cannot_update_an_application_on_another_hr_users_job(
    client: TestClient, job: Job, candidate: User, other_hr_user: User
) -> None:
    """Only the job's owner may move its applications."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.patch(
        f"{APPLICATIONS_URL}/{application_id}",
        json={"status": ApplicationStatus.ACCEPTED.value},
        headers=auth(other_hr_user),
    )

    assert response.status_code == 404


def test_candidate_cannot_update_their_own_status(
    client: TestClient, job: Job, candidate: User
) -> None:
    """A candidate must not be able to accept themselves."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.patch(
        f"{APPLICATIONS_URL}/{application_id}",
        json={"status": ApplicationStatus.ACCEPTED.value},
        headers=auth(candidate),
    )

    assert response.status_code == 403


def test_status_update_rejects_an_unknown_value(
    client: TestClient, job: Job, candidate: User, hr_user: User
) -> None:
    """Only the defined pipeline states are reachable."""
    application_id = apply_to(client, job, candidate).json()["id"]

    response = client.patch(
        f"{APPLICATIONS_URL}/{application_id}",
        json={"status": "HIRED_IMMEDIATELY"},
        headers=auth(hr_user),
    )

    assert response.status_code == 422


def test_deleting_a_job_removes_its_applications(
    client: TestClient, job: Job, candidate: User, hr_user: User, db_session: Session
) -> None:
    """CASCADE: an application to a deleted job would be a dangling row."""
    apply_to(client, job, candidate)

    client.delete(f"{JOBS_URL}/{job.id}", headers=auth(hr_user))

    assert db_session.query(Application).count() == 0
