"""Request and response shapes for authentication.

These types are the API's validation boundary. Fields the server controls —
id, is_active, timestamps — appear only on the way out, never on the way in, so
a caller cannot set them by adding them to a request body.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.user import FULL_NAME_MAX_LENGTH, UserRole

# Long enough that an offline attack on a leaked hash is expensive, short enough
# that a passphrase a person will actually remember still fits.
MIN_PASSWORD_LENGTH = 12


class UserCreate(BaseModel):
    """A registration request.

    Deliberately has no is_active or id field. Unknown keys in the body are
    ignored rather than assigned, so `{"is_active": false}` cannot create an
    account in a state the server never chose.
    """

    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX_LENGTH)
    role: UserRole

    @field_validator("password")
    @classmethod
    def _enforce_password_policy(cls, value: str) -> str:
        """Reject passwords that are too short, too long, or too simple.

        Enforced here rather than only in the browser: the API is reachable
        directly, so a client-side check alone is decoration.
        """
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )

        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")

        if not any(character.isalpha() for character in value):
            raise ValueError("Password must contain at least one letter.")

        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one digit.")

        return value


class LoginRequest(BaseModel):
    """A login attempt.

    The password carries no strength rules: an account created under an earlier
    policy must still be able to log in, and rejecting a weak password here
    would reveal that the policy had changed rather than that the guess was
    wrong.
    """

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """A user as returned to clients.

    Built by field selection rather than by dumping the ORM object, so a column
    added later — a password reset token, an internal note — cannot appear in a
    response simply because someone added it to the model.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """A successful login response."""

    access_token: str
    # S105 suppressed: the literal is the OAuth 2.0 token type name, not a
    # credential.
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
