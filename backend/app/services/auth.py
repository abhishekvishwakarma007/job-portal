"""Registration and credential checking.

Kept out of the route handlers so the rules are testable without HTTP and
reusable from a seed script or CLI. The handlers translate these exceptions
into status codes; they hold no policy of their own.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole

# Failures tolerated before the account starts locking. High enough that a
# person mistyping a password is unaffected, low enough that online guessing
# stalls almost immediately.
MAX_FAILED_LOGIN_ATTEMPTS = 5

# Progressive backoff: each failure past the threshold doubles the wait, so a
# sustained attack pays exponentially while a person who finally remembers
# their password waits a minute. Capped so an account is never bricked.
BASE_LOCKOUT_SECONDS = 60
MAX_LOCKOUT_SECONDS = 60 * 60


def _lockout_duration(failed_attempts: int) -> timedelta:
    """Seconds to lock for after this many consecutive failures."""
    excess = max(0, failed_attempts - MAX_FAILED_LOGIN_ATTEMPTS)
    seconds = min(BASE_LOCKOUT_SECONDS * (2**excess), MAX_LOCKOUT_SECONDS)
    return timedelta(seconds=seconds)


# A real bcrypt hash of a value no password can be. Verified against when no
# account matches, so a login for an unknown address costs the same ~200ms as
# one for a known address with a wrong password. Skipping it would leave a
# timing difference that answers "does this account exist?" just as clearly as
# a different status code would.
_ABSENT_USER_DUMMY_HASH = "$2b$12$Eeivm1bHS.0FopaLecENseVSrCj8KFF513FfRsU5JwylMWaPar3lK"


class EmailAlreadyRegisteredError(Exception):
    """Raised when an address already has an account."""


class InvalidCredentialsError(Exception):
    """Raised for any failed login.

    One exception covers unknown address, wrong password, and deactivated
    account: the caller must not be able to tell them apart.
    """


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
) -> User:
    """Create an account, refusing an address that already has one.

    The duplicate check is the database's UNIQUE index rather than a preceding
    SELECT: two concurrent registrations could both pass a check-then-insert and
    both commit, and the index is what makes that impossible rather than merely
    unlikely.
    """
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError(email) from exc

    db.refresh(user)
    return user


def _register_failed_attempt(db: Session, user: User) -> None:
    """Count a failure and lock the account once the threshold is passed."""
    user.failed_login_attempts += 1

    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(UTC) + _lockout_duration(
            user.failed_login_attempts
        )

    db.commit()


def _clear_failed_attempts(db: Session, user: User) -> None:
    """Reset the counter after a successful sign-in."""
    if user.failed_login_attempts == 0 and user.locked_until is None:
        return

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()


def is_locked(user: User, *, now: datetime | None = None) -> bool:
    """True while the account is inside a lockout window."""
    if user.locked_until is None:
        return False

    return user.locked_until > (now or datetime.now(UTC))


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Return the user when the credentials are valid, else raise.

    Deactivated and locked-out accounts fail here rather than at a later gate,
    so both take effect on the next attempt.

    Every failure mode raises the same exception, including lockout. Telling
    the caller "this account is locked" would confirm the address has an
    account, undoing the enumeration resistance the rest of this function is
    built around — so the lockout is silent, and the README says so.
    """
    # Matched on lower(email) so the lookup uses the same expression as the
    # unique index, and so someone who capitalised their address still gets in.
    user = db.execute(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _ABSENT_USER_DUMMY_HASH)
        raise InvalidCredentialsError

    # Checked before the password so a locked account cannot be probed for a
    # correct guess while it is locked — otherwise the lockout would slow an
    # attacker down without ever stopping them confirming a hit.
    if is_locked(user):
        raise InvalidCredentialsError

    if not verify_password(password, user.hashed_password):
        _register_failed_attempt(db, user)
        raise InvalidCredentialsError

    if not user.is_active:
        raise InvalidCredentialsError

    _clear_failed_attempts(db, user)
    return user
