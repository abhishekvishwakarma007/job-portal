"""Registration and credential checking.

Kept out of the route handlers so the rules are testable without HTTP and
reusable from a seed script or CLI. The handlers translate these exceptions
into status codes; they hold no policy of their own.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole

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


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Return the user when the credentials are valid, else raise.

    Deactivated accounts fail here rather than at a later gate, so disabling an
    account stops new sessions immediately.
    """
    # Matched on lower(email) so the lookup uses the same expression as the
    # unique index, and so someone who capitalised their address still gets in.
    user = db.execute(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _ABSENT_USER_DUMMY_HASH)
        raise InvalidCredentialsError

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InvalidCredentialsError

    return user
