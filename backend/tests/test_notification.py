"""In-app notification service.

These stand in for email, so the properties that matter are about who can send
to whom and who can read what — a message reaching the wrong inbox is the
failure this feature could actually cause.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.job import EmploymentType, Job
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.services.auth import register_user
from app.services.notification import (
    NotificationNotFoundError,
    count_unread,
    dismiss,
    list_notifications,
    mark_read,
    notify_applicant,
)

PASSWORD = "Str0ng@Password"


@pytest.fixture
def hr_user(db_session: Session) -> User:
    """The recruiter doing the messaging."""
    return register_user(
        db_session,
        email="hr@test.com",
        password=PASSWORD,
        full_name="Dana Reyes",
        role=UserRole.HR,
    )


@pytest.fixture
def candidate(db_session: Session) -> User:
    """The applicant being messaged."""
    return register_user(
        db_session,
        email="candidate@test.com",
        password=PASSWORD,
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    )


@pytest.fixture
def job(db_session: Session, hr_user: User) -> Job:
    """A posting owned by hr_user."""
    posting = Job(
        title="Senior Platform Engineer",
        company="Northwind Labs",
        description="Own the deployment pipeline.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        created_by_id=hr_user.id,
    )
    db_session.add(posting)
    db_session.commit()
    db_session.refresh(posting)
    return posting


@pytest.fixture
def application(db_session: Session, job: Job, candidate: User) -> Application:
    """An application from candidate to job."""
    submitted = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        cover_letter="Six years of pipeline work.",
    )
    db_session.add(submitted)
    db_session.commit()
    db_session.refresh(submitted)
    return submitted


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------


def test_message_reaches_the_applicant(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """Happy path."""
    notification = notify_applicant(
        db_session,
        application=application,
        job=job,
        sender=hr_user,
        message="We would like to invite you to a first interview.",
    )

    assert notification.user_id == candidate.id
    assert "first interview" in notification.body


def test_recipient_comes_from_the_application_not_the_caller(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """The decisive property.

    Taking the recipient from the application is what stops a message being
    addressed to someone who never applied — there is no parameter here that
    could carry an arbitrary user id.
    """
    other = register_user(
        db_session,
        email="stranger@test.com",
        password=PASSWORD,
        full_name="Ravi Menon",
        role=UserRole.CANDIDATE,
    )

    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    assert notification.user_id == candidate.id
    assert notification.user_id != other.id


def test_subject_names_the_role(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """An inbox of "Update on your application" tells nobody which one."""
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    assert job.title in notification.subject


def test_body_is_signed_by_the_sender(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """A candidate should know who wrote to them and on whose behalf."""
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    assert hr_user.full_name in notification.body
    assert job.company in notification.body


def test_a_new_message_starts_unread(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """Otherwise the badge would never appear."""
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    assert notification.is_read is False


def test_repr_does_not_leak_the_body(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """A message could contain anything; it must not reach a log line."""
    notification = notify_applicant(
        db_session,
        application=application,
        job=job,
        sender=hr_user,
        message="Salary discussion: we can offer 95,000.",
    )

    assert "95,000" not in repr(notification)


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def test_listing_returns_only_your_own(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """One user must never see another's inbox."""
    notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Yours."
    )

    theirs, total = list_notifications(db_session, user=candidate, limit=20, offset=0)
    mine, sender_total = list_notifications(db_session, user=hr_user, limit=20, offset=0)

    assert total == 1
    assert theirs[0].user_id == candidate.id
    # The sender does not receive a copy of what they sent.
    assert sender_total == 0
    assert mine == []


def test_listing_is_newest_first(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """Order is part of what the page renders."""
    for index in range(3):
        notify_applicant(
            db_session,
            application=application,
            job=job,
            sender=hr_user,
            message=f"Message {index}",
        )

    items, _ = list_notifications(db_session, user=candidate, limit=20, offset=0)

    assert "Message 2" in items[0].body
    assert "Message 0" in items[-1].body


def test_unread_count_tracks_reading(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """The header badge is this number."""
    first = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="One."
    )
    notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Two."
    )

    assert count_unread(db_session, user=candidate) == 2

    mark_read(db_session, first.id, user=candidate)

    assert count_unread(db_session, user=candidate) == 1


def test_marking_read_is_idempotent(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """A double-click must not error or double-count."""
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    mark_read(db_session, notification.id, user=candidate)
    mark_read(db_session, notification.id, user=candidate)

    assert count_unread(db_session, user=candidate) == 0


def test_cannot_mark_another_users_notification_read(
    db_session: Session, application: Application, job: Job, hr_user: User
) -> None:
    """Not found rather than forbidden.

    Telling one user that a given notification id exists is itself a
    disclosure, so the ownership predicate is part of the query.
    """
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )
    stranger = register_user(
        db_session,
        email="stranger@test.com",
        password=PASSWORD,
        full_name="Ravi Menon",
        role=UserRole.CANDIDATE,
    )

    with pytest.raises(NotificationNotFoundError):
        mark_read(db_session, notification.id, user=stranger)


def test_marking_an_unknown_notification_raises(
    db_session: Session, candidate: User
) -> None:
    """An id that was never issued must not 500."""
    with pytest.raises(NotificationNotFoundError):
        mark_read(db_session, uuid.uuid4(), user=candidate)


def test_pagination_limits_the_page(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """An unbounded inbox is a denial-of-service waiting to happen."""
    for index in range(5):
        notify_applicant(
            db_session,
            application=application,
            job=job,
            sender=hr_user,
            message=f"Message {index}",
        )

    items, total = list_notifications(db_session, user=candidate, limit=2, offset=0)

    assert len(items) == 2
    assert total == 5


def test_deleting_the_job_keeps_the_message(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """SET NULL, not CASCADE.

    Deleting a posting must not erase the record that someone was contacted
    about it — the message was still sent, and the candidate still received it.
    """
    notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    db_session.delete(job)
    db_session.commit()

    items, total = list_notifications(db_session, user=candidate, limit=20, offset=0)
    assert total == 1
    assert items[0].job_id is None


def test_deleting_the_recipient_removes_their_messages(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """CASCADE: a message to a deleted account is unreachable by definition."""
    notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    db_session.delete(candidate)
    db_session.commit()

    assert db_session.query(Notification).count() == 0


def test_dismissing_removes_the_notification(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """Dismiss deletes rather than hides — an inbox should be clearable."""
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )

    dismiss(db_session, notification.id, user=candidate)

    _, total = list_notifications(db_session, user=candidate, limit=20, offset=0)
    assert total == 0


def test_cannot_dismiss_another_users_notification(
    db_session: Session,
    application: Application,
    job: Job,
    hr_user: User,
    candidate: User,
) -> None:
    """Not found rather than forbidden, and the row must survive.

    Otherwise anyone holding an id could clear someone else's inbox.
    """
    notification = notify_applicant(
        db_session, application=application, job=job, sender=hr_user, message="Hello."
    )
    stranger = register_user(
        db_session,
        email="stranger2@test.com",
        password=PASSWORD,
        full_name="Lena Vogt",
        role=UserRole.CANDIDATE,
    )

    with pytest.raises(NotificationNotFoundError):
        dismiss(db_session, notification.id, user=stranger)

    _, total = list_notifications(db_session, user=candidate, limit=20, offset=0)
    assert total == 1


def test_dismissing_an_unknown_notification_raises(
    db_session: Session, candidate: User
) -> None:
    """An id that was never issued must not 500."""
    with pytest.raises(NotificationNotFoundError):
        dismiss(db_session, uuid.uuid4(), user=candidate)
