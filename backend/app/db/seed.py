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


# example.com is reserved for documentation (RFC 2606 §3), so these addresses
# can never route real mail. Not a .test/.local address: email-validator refuses
# those special-use TLDs, so EmailStr would reject the credentials at the API
# boundary and the seeded accounts could be created but never logged into.
# These credentials are published in the README and exist only for local
# review — seeding is skipped entirely in production.
# S106 is suppressed rather than silenced project-wide: these really are
# hardcoded credentials, and that is the point of a documented demo login. The
# rule should keep firing anywhere else it appears.
SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(
        email="hr@example.com",
        password="DemoPassw0rd!",  # noqa: S106
        full_name="Dana Reyes",
        role=UserRole.HR,
    ),
    SeedUser(
        email="candidate@example.com",
        password="DemoPassw0rd!",  # noqa: S106
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
        created = seed_users(session)
    finally:
        session.close()

    if created:
        logger.info("seed: created %d demo account(s)", len(created))
    else:
        logger.info("seed: demo accounts already present, nothing to do")

    return 0


if __name__ == "__main__":
    sys.exit(main())
