"""Candidate profile service.

The interesting cases are the ones a single-threaded read would miss: the
create-on-first-read racing itself, and a partial update blanking the sections
the caller did not mention.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import CandidateProfile
from app.models.user import User, UserRole
from app.schemas.profile import ProfileUpdate
from app.services import profile as profile_service
from app.services.auth import register_user
from app.services.profile import get_or_create_profile, update_profile

PASSWORD = "Str0ng@Password"


@pytest.fixture
def candidate(db_session: Session) -> User:
    """A candidate who may or may not have a profile yet."""
    return register_user(
        db_session,
        email="candidate@test.com",
        password=PASSWORD,
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    )


def test_first_read_creates_an_empty_profile(
    db_session: Session, candidate: User
) -> None:
    """Created on read rather than at registration.

    That way an account which never opens the page carries no empty row, and
    accounts predating the feature need no data migration.
    """
    profile = get_or_create_profile(db_session, user=candidate)

    assert profile.user_id == candidate.id
    assert profile.key_skills == ""
    assert profile.summary == ""


def test_second_read_returns_the_same_profile(
    db_session: Session, candidate: User
) -> None:
    """Reading twice must not leave two rows."""
    first = get_or_create_profile(db_session, user=candidate)
    second = get_or_create_profile(db_session, user=candidate)

    assert first.id == second.id
    assert db_session.query(CandidateProfile).count() == 1


def test_one_profile_per_candidate_is_enforced_by_the_database(
    db_session: Session, candidate: User
) -> None:
    """The constraint, not the service, is what makes the race impossible.

    Two concurrent first-reads can both find no profile and both insert. A
    check-then-create loses that race; the UNIQUE constraint cannot.
    """
    get_or_create_profile(db_session, user=candidate)
    db_session.add(CandidateProfile(user_id=candidate.id))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_losing_the_create_race_returns_the_existing_profile(
    db_session: Session, candidate: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service must survive losing the create race, not 500.

    Two requests arriving together — a page load and its first save, or a
    double-click — both find no profile and both insert. The constraint refuses
    the second; the service has to catch that and re-read.

    The lookup is stubbed to miss exactly once, which is what puts this in the
    loser's position: the row exists, the SELECT does not see it, so the insert
    is attempted and the IntegrityError path is genuinely taken.

    An earlier version of this test committed the row and then called the
    service, so the plain SELECT found it and the recovery path never ran. It
    passed against the unfixed code, which is the one thing a regression test
    must not do.
    """
    winner = CandidateProfile(user_id=candidate.id, headline="Written by the winner")
    db_session.add(winner)
    db_session.commit()

    real_find = profile_service._find_profile
    calls = {"count": 0}

    def find_missing_once(db: Session, *, user: User) -> CandidateProfile | None:
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return real_find(db, user=user)

    monkeypatch.setattr(profile_service, "_find_profile", find_missing_once)

    profile = get_or_create_profile(db_session, user=candidate)

    # Recovered by re-reading rather than raising, and no duplicate was left.
    assert calls["count"] == 2
    assert profile.headline == "Written by the winner"
    assert db_session.query(CandidateProfile).count() == 1


def test_a_constraint_violation_with_no_row_behind_it_still_raises(
    db_session: Session, candidate: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the race is recovered from, not every IntegrityError.

    If the lookup still finds nothing after the rollback, something other than
    the expected race failed. Swallowing that would turn a real fault into a
    silent one, so it is re-raised.
    """
    db_session.add(CandidateProfile(user_id=candidate.id))
    db_session.commit()

    monkeypatch.setattr(profile_service, "_find_profile", lambda db, *, user: None)

    with pytest.raises(IntegrityError):
        get_or_create_profile(db_session, user=candidate)


def test_profiles_are_separate_per_candidate(
    db_session: Session, candidate: User
) -> None:
    """One candidate's profile must never be handed to another."""
    other = register_user(
        db_session,
        email="other@test.com",
        password=PASSWORD,
        full_name="Ravi Menon",
        role=UserRole.CANDIDATE,
    )

    mine = get_or_create_profile(db_session, user=candidate)
    theirs = get_or_create_profile(db_session, user=other)

    assert mine.id != theirs.id
    assert theirs.user_id == other.id


def test_update_applies_the_supplied_fields(db_session: Session, candidate: User) -> None:
    """Happy path."""
    profile = get_or_create_profile(db_session, user=candidate)

    updated = update_profile(
        db_session,
        profile=profile,
        payload=ProfileUpdate(headline="Platform engineer", location="Bangalore"),
    )

    assert updated.headline == "Platform engineer"
    assert updated.location == "Bangalore"


def test_partial_update_leaves_other_sections_alone(
    db_session: Session, candidate: User
) -> None:
    """The decisive property.

    The UI saves one section at a time. Without exclude_unset every omitted
    field would arrive as None and wipe the rest of the profile — so saving a
    phone number would silently delete someone's employment history.
    """
    profile = get_or_create_profile(db_session, user=candidate)
    update_profile(
        db_session,
        profile=profile,
        payload=ProfileUpdate(summary="Six years of platform work.", key_skills="Docker"),
    )

    update_profile(
        db_session, profile=profile, payload=ProfileUpdate(phone="+91 98765 43210")
    )

    db_session.refresh(profile)
    assert profile.summary == "Six years of platform work."
    assert profile.key_skills == "Docker"
    assert profile.phone == "+91 98765 43210"


def test_skills_are_normalised_on_write(db_session: Session, candidate: User) -> None:
    """The matcher splits on commas, so the stored shape decides the term count.

    " React ,, react" is two skills or four depending on whether this runs.
    """
    profile = get_or_create_profile(db_session, user=candidate)

    updated = update_profile(
        db_session,
        profile=profile,
        payload=ProfileUpdate(key_skills=" Python ,, FastAPI ,Postgres , "),
    )

    assert updated.key_skills == "Python, FastAPI, Postgres"


def test_skill_list_splits_the_stored_value(db_session: Session, candidate: User) -> None:
    """What the ranking actually reads."""
    profile = get_or_create_profile(db_session, user=candidate)
    update_profile(
        db_session, profile=profile, payload=ProfileUpdate(key_skills="Python, Docker")
    )

    assert profile.skill_list() == ["Python", "Docker"]


def test_empty_skills_produce_an_empty_list(db_session: Session, candidate: User) -> None:
    """A blank field must not become a list containing one empty string."""
    profile = get_or_create_profile(db_session, user=candidate)

    assert profile.skill_list() == []


def test_update_persists_across_a_reload(db_session: Session, candidate: User) -> None:
    """Committed, not merely set on the in-memory object."""
    profile = get_or_create_profile(db_session, user=candidate)
    update_profile(
        db_session, profile=profile, payload=ProfileUpdate(headline="Engineer")
    )

    db_session.expire_all()
    reloaded = db_session.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate.id)
    ).scalar_one()

    assert reloaded.headline == "Engineer"


def test_deleting_the_user_removes_the_profile(
    db_session: Session, candidate: User
) -> None:
    """CASCADE: a profile without an account is unreachable by definition."""
    get_or_create_profile(db_session, user=candidate)

    db_session.delete(candidate)
    db_session.commit()

    assert db_session.query(CandidateProfile).count() == 0
