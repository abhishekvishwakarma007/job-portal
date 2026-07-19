"""Demo accounts for local and review environments.

The container entrypoint runs this on every boot, so it is written to be
repeatable rather than run-once: existing accounts are left exactly as they
are, and a concurrent second run loses the race harmlessly instead of crashing
the container.
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
from app.models.user import User, UserRole
from app.services.auth import EmailAlreadyRegisteredError, register_user

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedUser:
    """A demo account the README documents."""

    email: str
    password: str
    full_name: str
    role: UserRole


# The exact credentials the assessment brief publishes, reproduced verbatim so
# the assessor can type what the brief shows and get in. They exist only for
# local review — seeding is skipped entirely in production.
#
# A note on the domain, because it is a trap worth not falling into twice:
# the TLD must not be special-use. email-validator refuses .test, .local,
# .invalid and .example, so an address there is created here happily and then
# rejected by EmailStr at the API boundary — a documented login that cannot log
# in. test.com is an ordinary .com and validates.
#
# S106 is suppressed per-line rather than silenced project-wide: these really
# are hardcoded credentials, and that is the point of a documented demo login.
# The rule should keep firing anywhere else it appears.
SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(
        email="admin@test.com",
        password="Admin@1234",  # noqa: S106
        full_name="Dana Reyes",
        role=UserRole.HR,
    ),
    SeedUser(
        email="user@test.com",
        password="User@1234",  # noqa: S106
        full_name="Sam Okafor",
        role=UserRole.CANDIDATE,
    ),
)


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


@dataclass(frozen=True)
class SeedJob:
    """A demo posting owned by the seeded HR account."""

    title: str
    company: str
    description: str
    location: str
    employment_type: EmploymentType
    is_published: bool = True


# Enough variety that the browse, search, and filter paths all have something
# to act on, plus one draft so the published/draft distinction is visible in
# the HR view without anyone having to create it first.
SEED_JOBS: tuple[SeedJob, ...] = (
    SeedJob(
        title="Senior Platform Engineer",
        company="Northwind Labs",
        description=(
            "Own the deployment pipeline end to end: build, test, release.\n\n"
            "You will work across our Docker and CI tooling, and have real say "
            "in how we ship. We care more about judgement than a specific stack."
        ),
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
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
        title="Data Analyst Intern",
        company="Bluepeak Analytics",
        description=(
            "Help us understand where candidates drop out of the funnel.\n\n"
            "Six-month placement with a view to a permanent role."
        ),
        location="London",
        employment_type=EmploymentType.INTERNSHIP,
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
)

# The candidate arrives having already applied to one role, so "My
# applications" and the HR applicant pipeline both show real rows on a first
# look rather than an empty state.
# What the migration's server default leaves on rows that predate the column.
UNSET_COMPANY = "Confidential"

SEED_APPLICATION_JOB_TITLE = "Senior Platform Engineer"
SEED_APPLICATION_COVER_LETTER = (
    "I have run deployment pipelines for six years, most recently migrating a "
    "monolith to containerised services without a release freeze.\n\n"
    "The part of this role I care about is owning the pipeline end to end — "
    "that is where I do my best work."
)


def seed_jobs(db: Session, *, owner: User) -> list[Job]:
    """Create any missing demo postings, owned by the HR account.

    Matched on title per owner rather than a surrogate key, because the seed
    has no stable id to compare against and a title is what a reviewer would
    recognise as "already there".
    """
    created: list[Job] = []
    backfilled: list[Job] = []

    for spec in SEED_JOBS:
        existing = db.execute(
            select(Job).where(Job.title == spec.title, Job.created_by_id == owner.id)
        ).scalar_one_or_none()

        if existing is not None:
            # Backfill the company on a posting created before that column
            # existed, where the migration's server default left "Confidential".
            # Only that exact value is replaced, so a company an HR user typed
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
            logger.info("seed: created job %r (%s)", job.title, job.company)
        for job in backfilled:
            logger.info("seed: set company on %r to %r", job.title, job.company)

    return created


def seed_applications(db: Session, *, candidate: User) -> list[Application]:
    """Give the candidate one submitted application, if they have none.

    Skipped entirely when the candidate already holds any application: a
    reviewer who applied to something by hand should not find an extra row
    appearing on the next restart.
    """
    already_applied = db.execute(
        select(Application).where(Application.candidate_id == candidate.id).limit(1)
    ).scalar_one_or_none()

    if already_applied is not None:
        return []

    job = db.execute(
        select(Job).where(Job.title == SEED_APPLICATION_JOB_TITLE)
    ).scalar_one_or_none()

    if job is None:
        return []

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        cover_letter=SEED_APPLICATION_COVER_LETTER,
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    logger.info("seed: created application to %r", job.title)
    return [application]


def _find_user(db: Session, role: UserRole) -> User | None:
    """Return the seeded account for a role, whether or not this run made it."""
    email = next(spec.email for spec in SEED_USERS if spec.role is role)

    return db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    ).scalar_one_or_none()


def main() -> int:
    """Entrypoint hook: seed unless this is production.

    Publishing known credentials into a production database would be handing out
    a working login, so the environment gates the whole operation.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()

    if settings.is_production:
        logger.info("seed: skipped, ENVIRONMENT is production")
        return 0

    session = get_session_factory()()
    try:
        created_users = seed_users(session)

        # Looked up rather than taken from created_users: on a restart the
        # accounts already exist, so seed_users returns nothing and the jobs
        # would never be seeded if this depended on its return value.
        hr_user = _find_user(session, UserRole.HR)
        candidate = _find_user(session, UserRole.CANDIDATE)

        created_jobs = seed_jobs(session, owner=hr_user) if hr_user else []
        created_applications = (
            seed_applications(session, candidate=candidate) if candidate else []
        )
    finally:
        session.close()

    if created_users or created_jobs or created_applications:
        logger.info(
            "seed: created %d account(s), %d job(s), %d application(s)",
            len(created_users),
            len(created_jobs),
            len(created_applications),
        )
    else:
        logger.info("seed: demo data already present, nothing to do")

    return 0


if __name__ == "__main__":
    sys.exit(main())
