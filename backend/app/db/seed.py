"""Demo data for local and review environments.

The container entrypoint runs this on every boot, so it is written to be
repeatable rather than run-once: existing rows are left exactly as they are,
and a concurrent second run loses the race harmlessly instead of crashing the
container.

Shaped so a reviewer opening the app finds it populated — several employers, a
spread of roles, candidates with filled-in profiles, and applications already
in the pipeline. An empty install makes working features look missing.
"""

import logging
import sys
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.application import Application, ApplicationStatus
from app.models.job import EmploymentType, Job
from app.models.profile import CandidateProfile
from app.models.user import User, UserRole
from app.services.auth import EmailAlreadyRegisteredError, register_user

logger = logging.getLogger(__name__)

# What the company column's migration default leaves on rows predating it.
UNSET_COMPANY = "Confidential"


@dataclass(frozen=True)
class SeedProfile:
    """The profile a seeded candidate arrives with."""

    headline: str = ""
    location: str = ""
    phone: str = ""
    summary: str = ""
    preferred_role: str = ""
    preferred_location: str = ""
    preferred_employment_type: str = ""
    key_skills: str = ""
    employment: str = ""
    education: str = ""


@dataclass(frozen=True)
class SeedUser:
    """A demo account."""

    email: str
    password: str
    full_name: str
    role: UserRole
    # HR only. Every posting this account owns carries it, so one recruiter
    # represents one employer — which is what makes the company filter and the
    # per-owner pipeline views show anything meaningful.
    company: str = ""
    profile: SeedProfile | None = None


@dataclass(frozen=True)
class SeedJob:
    """A demo posting, owned by the HR account at the same company."""

    title: str
    company: str
    description: str
    location: str
    employment_type: EmploymentType
    is_published: bool = True


@dataclass(frozen=True)
class SeedApplication:
    """A demo application, matched to job and candidate by natural key."""

    job_title: str
    candidate_email: str
    cover_letter: str
    status: ApplicationStatus = ApplicationStatus.SUBMITTED


# The two credentials the assessment brief publishes come first and are
# reproduced verbatim — an assessor should be able to type what the brief shows
# and get in.
#
# A note on the domain, because it is a trap worth not falling into twice: the
# TLD must not be special-use. email-validator refuses .test, .local, .invalid
# and .example, so an address there is created here happily and then rejected
# by EmailStr at the API boundary — a documented login that cannot log in.
# test.com is an ordinary .com and validates.
#
# S106 is suppressed per line rather than silenced project-wide: these really
# are hardcoded credentials, and that is the point of a documented demo login.
SEED_USERS: tuple[SeedUser, ...] = (
    # --- HR, one account per employer ---
    SeedUser(
        email="admin@test.com",
        password="Admin@1234",  # noqa: S106
        full_name="Dana Reyes",
        role=UserRole.HR,
        company="Northwind Labs",
    ),
    SeedUser(
        email="hr.kestrel@test.com",
        password="Kestrel@1234",  # noqa: S106
        full_name="Priya Nair",
        role=UserRole.HR,
        company="Kestrel Studio",
    ),
    SeedUser(
        email="hr.bluepeak@test.com",
        password="Bluepeak@1234",  # noqa: S106
        full_name="Marcus Feld",
        role=UserRole.HR,
        company="Bluepeak Analytics",
    ),
    # --- Candidates ---
    SeedUser(
        email="user@test.com",
        password="User@1234",  # noqa: S106
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
        profile=SeedProfile(
            headline="Platform engineer, six years shipping containerised services",
            location="Bangalore",
            phone="+91 98765 43210",
            summary=(
                "I own deployment pipelines end to end — build, test, release. "
                "Most recently migrated a monolith to containerised services "
                "without a release freeze."
            ),
            preferred_role="Platform Engineer",
            preferred_location="Remote",
            preferred_employment_type=EmploymentType.FULL_TIME.value,
            key_skills="Python, Docker, Postgres, CI, Kubernetes, FastAPI",
            employment=(
                "Platform Engineer, Helio Systems, 2022-present\n"
                "Backend Developer, Marlin Software, 2019-2022"
            ),
            education="B.Tech Computer Science, NIT Trichy, 2019",
        ),
    ),
    SeedUser(
        email="ravi@test.com",
        password="Ravi@1234",  # noqa: S106
        full_name="Ravi Menon",
        role=UserRole.CANDIDATE,
        profile=SeedProfile(
            headline="Backend engineer focused on APIs and data modelling",
            location="Pune",
            summary=(
                "I build APIs that are pleasant to consume and boring to "
                "operate. Strong on relational modelling, and on tests that "
                "assert behaviour rather than implementation."
            ),
            preferred_role="Backend Engineer",
            preferred_location="Pune",
            preferred_employment_type=EmploymentType.FULL_TIME.value,
            key_skills="Python, FastAPI, Postgres, SQLAlchemy, pytest",
            employment="Backend Engineer, Corvus Retail, 2021-present",
            education="B.E. Information Technology, COEP Pune, 2021",
        ),
    ),
    SeedUser(
        email="lena@test.com",
        password="Lena@1234",  # noqa: S106
        full_name="Lena Vogt",
        role=UserRole.CANDIDATE,
        profile=SeedProfile(
            headline="Product designer for hiring and marketplace products",
            location="Berlin",
            summary=(
                "I design flows end to end and work directly with engineering. "
                "Most of my work has been on two-sided products, where both "
                "audiences need different things from the same screen."
            ),
            preferred_role="Product Designer",
            preferred_location="Berlin",
            preferred_employment_type=EmploymentType.CONTRACT.value,
            key_skills="Figma, Design systems, Prototyping, User research",
            employment="Product Designer, Halden Studio, 2020-present",
            education="MA Interaction Design, UdK Berlin, 2020",
        ),
    ),
    SeedUser(
        email="amara@test.com",
        password="Amara@1234",  # noqa: S106
        full_name="Amara Diallo",
        role=UserRole.CANDIDATE,
        profile=SeedProfile(
            headline="Final-year statistics student seeking a first analytics role",
            location="London",
            summary=(
                "Final-year statistics student. I like questions about where "
                "people drop out of a funnel and what would move them through."
            ),
            preferred_role="Data Analyst",
            preferred_location="London",
            preferred_employment_type=EmploymentType.INTERNSHIP.value,
            key_skills="SQL, Python, pandas, Statistics, Visualisation",
            employment="Data intern, Civic Insight, summer 2025",
            education="BSc Statistics, UCL, expected 2026",
        ),
    ),
)


SEED_JOBS: tuple[SeedJob, ...] = (
    SeedJob(
        title="Senior Platform Engineer",
        company="Northwind Labs",
        description=(
            "Own the deployment pipeline end to end: build, test, release.\n\n"
            "You will work across our Docker and Postgres tooling and have real "
            "say in how we ship. We care more about judgement than about a "
            "specific stack."
        ),
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
    ),
    SeedJob(
        title="Backend Engineer (Python)",
        company="Northwind Labs",
        description=(
            "Build the APIs behind our hiring product.\n\n"
            "FastAPI, Postgres, and a strong bias toward tests that assert "
            "behaviour rather than implementation."
        ),
        location="Bangalore",
        employment_type=EmploymentType.FULL_TIME,
    ),
    SeedJob(
        title="Engineering Manager",
        company="Northwind Labs",
        description=(
            "Not yet advertised — this posting is a draft.\n\n"
            "It exists so the draft state is visible in the HR view without "
            "anyone needing to create one."
        ),
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        is_published=False,
    ),
    SeedJob(
        title="Product Designer",
        company="Kestrel Studio",
        description=(
            "Shape the candidate experience from first search to offer.\n\n"
            "You will own flows end to end and work directly with engineering. "
            "Portfolio matters more than years."
        ),
        location="Berlin",
        employment_type=EmploymentType.CONTRACT,
    ),
    SeedJob(
        title="Frontend Engineer (React)",
        company="Kestrel Studio",
        description=(
            "Build the interfaces our candidates and hiring teams live in.\n\n"
            "React and TypeScript, with accessibility treated as a requirement "
            "rather than a later pass."
        ),
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
    ),
    SeedJob(
        title="Data Analyst Intern",
        company="Bluepeak Analytics",
        description=(
            "Help us understand where candidates drop out of the funnel.\n\n"
            "Six-month placement with a view to a permanent role. SQL and "
            "Python, and a willingness to ask why a number moved."
        ),
        location="London",
        employment_type=EmploymentType.INTERNSHIP,
    ),
)


SEED_APPLICATIONS: tuple[SeedApplication, ...] = (
    SeedApplication(
        job_title="Senior Platform Engineer",
        candidate_email="user@test.com",
        cover_letter=(
            "I have run deployment pipelines for six years, most recently "
            "migrating a monolith to containerised services without a release "
            "freeze.\n\n"
            "The part of this role I care about is owning the pipeline end to "
            "end — that is where I do my best work."
        ),
    ),
    SeedApplication(
        job_title="Backend Engineer (Python)",
        candidate_email="ravi@test.com",
        cover_letter=(
            "FastAPI and Postgres are what I reach for daily, and I care about "
            "APIs being boring to operate.\n\n"
            "I would like to work somewhere that treats tests as a design tool "
            "rather than a chore."
        ),
        status=ApplicationStatus.UNDER_REVIEW,
    ),
    SeedApplication(
        job_title="Backend Engineer (Python)",
        candidate_email="user@test.com",
        cover_letter=(
            "Platform work has kept me close to the API layer, and I would "
            "like to move back toward building it."
        ),
    ),
    SeedApplication(
        job_title="Product Designer",
        candidate_email="lena@test.com",
        cover_letter=(
            "Two-sided hiring products are exactly what I have spent the last "
            "four years on.\n\n"
            "I would want to start by watching candidates use what exists."
        ),
        status=ApplicationStatus.ACCEPTED,
    ),
    SeedApplication(
        job_title="Data Analyst Intern",
        candidate_email="amara@test.com",
        cover_letter=(
            "Funnel drop-off is the question I find most interesting, and it "
            "is what my dissertation is about.\n\n"
            "SQL and pandas are where I am strongest."
        ),
    ),
)


def _profile_fields(profile: SeedProfile) -> dict[str, str]:
    """The profile spec as column values."""
    return {
        "headline": profile.headline,
        "location": profile.location,
        "phone": profile.phone,
        "summary": profile.summary,
        "preferred_role": profile.preferred_role,
        "preferred_location": profile.preferred_location,
        "preferred_employment_type": profile.preferred_employment_type,
        "key_skills": profile.key_skills,
        "employment": profile.employment,
        "education": profile.education,
    }


def seed_users(db: Session) -> list[User]:
    """Create any missing demo accounts and return those created.

    Existing accounts are skipped rather than updated: a reviewer who changed a
    password mid-session should not find it reverted by the next restart.

    The lookup is matched on lower(email) so it uses the same expression as the
    unique index — and the insert still catches the duplicate error, because two
    containers starting together can both pass the check before either commits.
    """
    created: list[User] = []

    for spec in SEED_USERS:
        existing = db.execute(
            select(User).where(func.lower(User.email) == spec.email.lower())
        ).scalar_one_or_none()

        if existing is not None:
            continue

        try:
            user = register_user(
                db,
                email=spec.email,
                password=spec.password,
                full_name=spec.full_name,
                role=spec.role,
            )
        except EmailAlreadyRegisteredError:
            # Another process seeded it between our check and our insert. The
            # account exists either way, which is all this function promises.
            logger.info("seed: %s already created by another process", spec.email)
            continue

        created.append(user)
        logger.info("seed: created %s (%s)", spec.email, spec.role.value)

    return created


def seed_profiles(
    db: Session, *, users_by_email: dict[str, User]
) -> list[CandidateProfile]:
    """Give seeded candidates a filled-in profile.

    Profiles feed the HR shortlist, so seeding them is what makes the ranking
    show a real spread rather than every applicant scoring on cover letter
    alone.

    A profile with content is left alone, so a reviewer's own edits survive a
    restart. One created empty by a first visit to the profile page is filled
    in, since populating it overwrites nothing.
    """
    created: list[CandidateProfile] = []

    for spec in SEED_USERS:
        if spec.profile is None:
            continue

        user = users_by_email.get(spec.email.lower())
        if user is None:
            continue

        profile = db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        ).scalar_one_or_none()

        if profile is None:
            profile = CandidateProfile(user_id=user.id, **_profile_fields(spec.profile))
            db.add(profile)
            created.append(profile)
        elif not profile.key_skills and not profile.summary:
            for column, value in _profile_fields(spec.profile).items():
                setattr(profile, column, value)
            created.append(profile)

    if created:
        db.commit()
        logger.info("seed: filled %d candidate profile(s)", len(created))

    return created


def seed_jobs(db: Session, *, users_by_email: dict[str, User]) -> list[Job]:
    """Create any missing demo postings under the HR account for their company.

    Ownership is resolved by company rather than assigning everything to one
    recruiter: an HR account represents an employer, so Kestrel's designer role
    belongs to Kestrel's recruiter. That is also what gives the company filter
    and the per-owner pipeline views something to distinguish.
    """
    hr_by_company = {
        spec.company: users_by_email[spec.email.lower()]
        for spec in SEED_USERS
        if spec.role is UserRole.HR and spec.email.lower() in users_by_email
    }

    created: list[Job] = []
    backfilled: list[Job] = []

    for spec in SEED_JOBS:
        owner = hr_by_company.get(spec.company)
        if owner is None:
            continue

        existing = db.execute(
            select(Job).where(Job.title == spec.title)
        ).scalar_one_or_none()

        if existing is not None:
            # Backfill a posting created before the company column existed,
            # where the migration's server default left "Confidential". Only
            # that exact value is replaced, so a company an HR user typed
            # themselves is never overwritten.
            if existing.company == UNSET_COMPANY:
                existing.company = spec.company
                backfilled.append(existing)
            continue

        job = Job(
            title=spec.title,
            company=spec.company,
            description=spec.description,
            location=spec.location,
            employment_type=spec.employment_type,
            is_published=spec.is_published,
            created_by_id=owner.id,
        )
        db.add(job)
        created.append(job)

    if created or backfilled:
        db.commit()
        for job in created:
            db.refresh(job)
            logger.info("seed: created job %r at %s", job.title, job.company)
        for job in backfilled:
            logger.info("seed: set company on %r to %r", job.title, job.company)

    return created


def seed_applications(
    db: Session, *, users_by_email: dict[str, User]
) -> list[Application]:
    """Put applications in the pipeline, across several jobs and statuses.

    Spread over statuses so the HR pipeline and the candidate's status view
    both show more than one state on a first look.

    Each is skipped when that candidate already applied to that job — the
    unique constraint would refuse it anyway, and catching it here keeps a
    restart quiet rather than noisy.
    """
    created: list[Application] = []

    for spec in SEED_APPLICATIONS:
        candidate = users_by_email.get(spec.candidate_email.lower())
        if candidate is None:
            continue

        job = db.execute(
            select(Job).where(Job.title == spec.job_title)
        ).scalar_one_or_none()
        if job is None:
            continue

        already = db.execute(
            select(Application).where(
                Application.job_id == job.id,
                Application.candidate_id == candidate.id,
            )
        ).scalar_one_or_none()
        if already is not None:
            continue

        application = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            cover_letter=spec.cover_letter,
            status=spec.status,
        )
        db.add(application)
        created.append(application)

    if created:
        db.commit()
        logger.info("seed: created %d application(s)", len(created))

    return created


def _users_by_email(db: Session) -> dict[str, User]:
    """Every seeded account, keyed by lower-cased email.

    Read back rather than taken from seed_users' return value: on a restart the
    accounts already exist, so that list is empty and everything downstream
    would be skipped.
    """
    emails = [spec.email.lower() for spec in SEED_USERS]

    return {
        user.email.lower(): user
        for user in db.execute(
            select(User).where(func.lower(User.email).in_(emails))
        ).scalars()
    }


def main() -> int:
    """Entrypoint hook: seed unless this is production.

    Publishing known credentials into a production database would be handing out
    working logins, so the environment gates the whole operation.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()

    if settings.is_production:
        logger.info("seed: skipped, ENVIRONMENT is production")
        return 0

    session = get_session_factory()()
    try:
        created_users = seed_users(session)
        users = _users_by_email(session)

        created_profiles = seed_profiles(session, users_by_email=users)
        created_jobs = seed_jobs(session, users_by_email=users)
        created_applications = seed_applications(session, users_by_email=users)
    finally:
        session.close()

    if created_users or created_profiles or created_jobs or created_applications:
        logger.info(
            "seed: %d account(s), %d profile(s), %d job(s), %d application(s)",
            len(created_users),
            len(created_profiles),
            len(created_jobs),
            len(created_applications),
        )
    else:
        logger.info("seed: demo data already present, nothing to do")

    return 0


if __name__ == "__main__":
    sys.exit(main())
