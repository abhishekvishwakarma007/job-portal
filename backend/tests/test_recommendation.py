"""Applicant ranking.

The scoring is a keyword overlap, so the tests are less about arithmetic than
about the properties that keep the number honest: that padding cannot inflate
it, that a listed skill outweighs a passing mention, and that the order does
not shift between identical calls.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.application import Application
from app.models.job import EmploymentType, Job
from app.models.profile import CandidateProfile
from app.services.recommendation import (
    rank_applications,
    score_application,
)


def make_job(title: str = "Senior Platform Engineer", description: str = "") -> Job:
    """An unsaved job with controllable vocabulary."""
    return Job(
        id=uuid.uuid4(),
        title=title,
        company="Northwind Labs",
        description=description or "Own the deployment pipeline using Docker.",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        is_published=True,
        created_by_id=uuid.uuid4(),
    )


def make_application(
    cover_letter: str, *, created_at: datetime | None = None
) -> Application:
    """An unsaved application carrying the given letter."""
    application = Application(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        cover_letter=cover_letter,
    )
    application.created_at = created_at or datetime.now(UTC)
    return application


def make_profile(key_skills: str = "", summary: str = "") -> CandidateProfile:
    """An unsaved profile with the fields the ranking reads."""
    return CandidateProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        key_skills=key_skills,
        summary=summary,
        preferred_role="",
        employment="",
    )


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def test_no_overlap_scores_zero() -> None:
    """A letter about something else must not score."""
    job = make_job(description="Deployment pipeline work with Docker.")

    score, matched = score_application(
        job, make_application("I enjoy gardening and watercolour painting.")
    )

    assert score == 0.0
    assert matched == []


def test_overlapping_terms_score_above_zero() -> None:
    """Shared vocabulary is what the score is measuring."""
    job = make_job(description="Deployment pipeline work with Docker.")

    score, matched = score_application(
        job, make_application("I have run deployment pipelines with Docker.")
    )

    assert score > 0
    assert "docker" in matched


def test_stop_words_do_not_count_as_a_match() -> None:
    """Matching on common words would score every applicant identically.

    A letter made only of connective tissue shares plenty of words with any
    posting; if those counted, ranking would be noise.
    """
    job = make_job(description="Own the deployment pipeline.")

    score, matched = score_application(
        job, make_application("I have been working with the team and we can use it.")
    )

    assert score == 0.0
    assert matched == []


def test_padding_a_letter_cannot_inflate_the_score() -> None:
    """The decisive property.

    The denominator is the posting's vocabulary, not the candidate's, so a
    thousand irrelevant words add nothing. Were it the other way round, the
    wordiest applicant would win every shortlist.
    """
    job = make_job(description="Deployment pipeline work with Docker.")
    letter = "I have run deployment pipelines with Docker."

    plain = score_application(job, make_application(letter))[0]
    padded = score_application(
        job, make_application(f"{letter} {'kangaroo tapestry rhubarb ' * 200}")
    )[0]

    assert padded == plain


def test_a_listed_skill_outweighs_a_passing_mention() -> None:
    """Naming a skill is a stronger claim than using the word in a sentence.

    Without this weighting a wordy letter beats a candidate who actually has
    the skill, which is the opposite of what a shortlist is for.
    """
    job = make_job(description="Deployment pipeline work with Docker and Postgres.")
    letter = "I work with docker and postgres."

    without_profile = score_application(job, make_application(letter))[0]
    with_skills = score_application(
        job, make_application(letter), make_profile(key_skills="Docker, Postgres")
    )[0]

    assert with_skills > without_profile


def test_profile_terms_count_even_when_absent_from_the_letter() -> None:
    """A profile is the more durable signal — a letter is written for one role."""
    job = make_job(description="Deployment pipeline work with Kubernetes.")
    letter = "I would like to hear more about this position."

    without_profile = score_application(job, make_application(letter))[0]
    with_profile = score_application(
        job, make_application(letter), make_profile(key_skills="Kubernetes")
    )

    assert without_profile == 0.0
    assert with_profile[0] > 0
    assert "kubernetes" in with_profile[1]


def test_score_never_exceeds_one() -> None:
    """Skills weigh double, so the cap is what keeps the score a share.

    Without it a fully-matching skilled candidate would score 2.0, and a
    percentage rendered from that reads as 200%.
    """
    job = make_job(title="Docker", description="Docker Postgres Kubernetes.")

    score, _ = score_application(
        job,
        make_application("Docker Postgres Kubernetes."),
        make_profile(key_skills="Docker, Postgres, Kubernetes"),
    )

    assert 0.0 <= score <= 1.0


def test_matching_is_case_insensitive() -> None:
    """Nobody capitalises their skills the same way a posting does."""
    job = make_job(description="Work with DOCKER and Postgres.")

    score, matched = score_application(job, make_application("docker, postgres"))

    assert score > 0
    assert "docker" in matched


def test_a_job_with_no_usable_vocabulary_scores_zero() -> None:
    """Guards the division: an empty denominator must not raise."""
    job = make_job(title="a", description="the and or")

    score, matched = score_application(job, make_application("anything at all"))

    assert score == 0.0
    assert matched == []


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------


def test_better_matches_rank_first() -> None:
    """The whole point of the endpoint."""
    job = make_job(description="Deployment pipeline work with Docker and Postgres.")
    weak = make_application("I am interested in this position.")
    strong = make_application("Deployment pipeline, Docker and Postgres daily.")

    ranked = rank_applications(job, [weak, strong], limit=10)

    assert ranked[0].application is strong


def test_limit_truncates_the_shortlist() -> None:
    """A shortlist that returns everyone is not a shortlist."""
    job = make_job()
    applications = [make_application(f"Docker pipeline {i}") for i in range(5)]

    assert len(rank_applications(job, applications, limit=2)) == 2


def test_ties_break_on_who_applied_first() -> None:
    """Order must be stable, or the page reshuffles on every refresh."""
    job = make_job()
    now = datetime.now(UTC)
    earlier = make_application("Docker pipeline.", created_at=now - timedelta(hours=1))
    later = make_application("Docker pipeline.", created_at=now)

    ranked = rank_applications(job, [later, earlier], limit=10)

    assert [item.application for item in ranked] == [earlier, later]


def test_ranking_is_stable_across_calls() -> None:
    """Same input, same order — asserted rather than assumed."""
    job = make_job()
    now = datetime.now(UTC)
    applications = [
        make_application(f"Docker {index}", created_at=now + timedelta(seconds=index))
        for index in range(4)
    ]

    first = [
        item.application.id for item in rank_applications(job, applications, limit=4)
    ]
    second = [
        item.application.id for item in rank_applications(job, applications, limit=4)
    ]

    assert first == second


def test_profiles_are_matched_to_their_own_candidate() -> None:
    """A profile must not lift a different applicant's score.

    The lookup is by candidate id, so this pins that the mapping is keyed
    correctly rather than, say, by position in the list.
    """
    job = make_job(description="Kubernetes and Docker pipeline work.")
    skilled = make_application("Interested in the role.")
    unskilled = make_application("Interested in the role.")

    ranked = rank_applications(
        job,
        [skilled, unskilled],
        limit=10,
        profiles={str(skilled.candidate_id): make_profile(key_skills="Kubernetes")},
    )

    assert ranked[0].application is skilled
    assert ranked[1].score == 0.0


def test_ranking_without_profiles_still_works() -> None:
    """Profiles are optional — an applicant who filled none in still ranks."""
    job = make_job()

    ranked = rank_applications(job, [make_application("Docker pipeline.")], limit=10)

    assert len(ranked) == 1


def test_ranking_an_empty_pipeline_returns_nothing() -> None:
    """A posting nobody applied to must not raise."""
    assert rank_applications(make_job(), [], limit=3) == []


@pytest.mark.parametrize("limit", [1, 3, 100])
def test_limit_is_respected_for_any_size(limit: int) -> None:
    """Asking for more than exists returns what exists, not an error."""
    job = make_job()
    applications = [make_application("Docker") for _ in range(3)]

    assert len(rank_applications(job, applications, limit=limit)) == min(limit, 3)
