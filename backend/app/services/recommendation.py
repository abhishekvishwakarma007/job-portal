"""Ranking applicants against a posting.

Deliberately simple: a term-overlap score between the posting's text and the
candidate's cover letter, with no model, no embedding service, and no external
call. It is honest about what it is — a keyword match, not a judgement of
suitability — and the API labels it as such so nobody mistakes the number for
something it is not.

The shape is what matters: a service that takes a job and its applications and
returns them ranked. Swapping this for a real relevance model later means
replacing one function, not rewriting the endpoint or the UI.
"""

import re
from dataclasses import dataclass

from app.models.application import Application
from app.models.job import Job
from app.models.profile import CandidateProfile

# Words too common to carry signal. Matching on them would score every
# applicant identically, which is the same as not ranking at all.
_STOP_WORDS = frozenset(
    """
    a an and are as at be been build building by can for from has have how in
    into is it its of on or our over role team that the their them they this
    to up use used using we what when where which who will with within work
    working you your years year experience strong good great across most
    recently
    """.split()
)

# Two-character tokens are almost always noise ("go" being the notable
# exception, which this accepts losing).
_MIN_TERM_LENGTH = 3


@dataclass(frozen=True)
class RankedApplication:
    """One applicant with the score that placed them."""

    application: Application
    score: float
    matched_terms: list[str]


def _terms(text: str) -> set[str]:
    """Reduce free text to a set of comparable terms."""
    words = re.findall(r"[a-z0-9+#.]+", text.lower())

    return {
        word.strip(".")
        for word in words
        if len(word) >= _MIN_TERM_LENGTH and word not in _STOP_WORDS
    }


def score_application(
    job: Job,
    application: Application,
    profile: CandidateProfile | None = None,
) -> tuple[float, list[str]]:
    """Return how well a candidate overlaps the posting, and on what.

    Draws on the cover letter plus, when the candidate has filled one in, their
    profile: key skills, summary, preferred role, and employment history. A
    profile is the more durable signal — a letter is written for one posting,
    while skills describe the person — so this reads both and takes the union.

    Listed skills count double. Someone naming "postgres" as a skill is making
    a stronger claim than someone who happened to use the word in a sentence,
    and weighting is what stops a wordy letter outranking a matching one.

    The denominator is the posting's vocabulary, not the candidate's, so
    padding either text with unrelated words cannot inflate the score — only
    covering more of what the posting actually asks for can.
    """
    job_terms = _terms(f"{job.title} {job.description}")

    if not job_terms:
        return 0.0, []

    candidate_terms = _terms(application.cover_letter)
    skill_terms: set[str] = set()

    if profile is not None:
        skill_terms = _terms(" ".join(profile.skill_list()))
        candidate_terms |= skill_terms
        candidate_terms |= _terms(
            f"{profile.summary} {profile.preferred_role} {profile.employment}"
        )

    matched = job_terms & candidate_terms

    if not matched:
        return 0.0, []

    # Skills weigh double, capped at 1.0 so a score stays a share of the
    # posting rather than becoming an unbounded number.
    weight = len(matched) + len(matched & skill_terms)
    score = min(weight / len(job_terms), 1.0)

    return score, sorted(matched)


def rank_applications(
    job: Job,
    applications: list[Application],
    *,
    limit: int,
    profiles: dict[str, CandidateProfile] | None = None,
) -> list[RankedApplication]:
    """Return the best-matching applicants first.

    Ties break on who applied earlier, so the ordering is stable between calls
    rather than shifting each time the page is refreshed.
    """
    by_candidate = profiles or {}

    ranked = [
        RankedApplication(
            application=application,
            score=score,
            matched_terms=matched,
        )
        for application in applications
        for score, matched in [
            score_application(
                job, application, by_candidate.get(str(application.candidate_id))
            )
        ]
    ]

    ranked.sort(key=lambda item: (-item.score, item.application.created_at))

    return ranked[:limit]
