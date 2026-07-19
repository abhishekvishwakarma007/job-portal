"""Password hashing and token signing.

These are the primitives every authorisation decision rests on, so each
property is asserted directly rather than inferred from endpoint behaviour.
"""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    ALGORITHM,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import UserRole

PASSWORD = "correct-horse-battery-staple-7"


def test_hash_does_not_contain_the_password(valid_env: None) -> None:
    """The stored value must not reveal the input, even partially."""
    hashed = hash_password(PASSWORD)

    assert PASSWORD not in hashed


def test_hash_is_bcrypt_shaped(valid_env: None) -> None:
    """Pin the algorithm: a change here silently invalidates every stored hash."""
    hashed = hash_password(PASSWORD)

    assert hashed.startswith("$2b$")
    assert len(hashed) == 60


def test_same_password_hashes_differently_each_time(valid_env: None) -> None:
    """A per-hash salt is what stops a rainbow table working across accounts."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_accepts_the_original_password(valid_env: None) -> None:
    """The happy path: the salt travels inside the hash, so verify round-trips."""
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_verify_rejects_a_wrong_password(valid_env: None) -> None:
    """The whole point of the primitive."""
    assert verify_password("not-the-password", hash_password(PASSWORD)) is False


def test_verify_rejects_a_malformed_hash(valid_env: None) -> None:
    """A corrupted or truncated hash must fail closed, not raise.

    A stored value could be damaged by a bad migration. Raising here would turn
    one broken row into a 500 on every login attempt against it.
    """
    assert verify_password(PASSWORD, "not-a-bcrypt-hash") is False


def test_rejects_password_beyond_the_bcrypt_limit(valid_env: None) -> None:
    """bcrypt silently truncates past 72 bytes, so refuse rather than mislead.

    Without this, "<72 bytes>abc" and "<72 bytes>xyz" would be the same
    credential and either would open the account.
    """
    with pytest.raises(ValueError, match="72"):
        hash_password("a" * 73)


def test_token_round_trips_subject_and_role(valid_env: None) -> None:
    """Role rides in the token so routine authorisation needs no DB read."""
    user_id = uuid.uuid4()

    payload = decode_access_token(create_access_token(user_id=user_id, role=UserRole.HR))

    assert payload.user_id == user_id
    assert payload.role is UserRole.HR


def test_token_carries_an_expiry(valid_env: None) -> None:
    """A token without exp never stops being valid."""
    token = create_access_token(user_id=uuid.uuid4(), role=UserRole.CANDIDATE)

    claims = jwt.decode(token, options={"verify_signature": False})

    assert "exp" in claims


def test_expired_token_is_rejected(valid_env: None) -> None:
    """Expiry must be enforced on decode, not merely present in the payload."""
    token = create_access_token(
        user_id=uuid.uuid4(),
        role=UserRole.HR,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected(valid_env: None) -> None:
    """The signature is the only thing making a token's claims trustworthy.

    An attacker who could mint tokens with their own key would simply assert
    `role: HR` and walk in.
    """
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "HR", "exp": 9999999999},
        "an-attackers-own-signing-key-32-chars",
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_tampered_token_is_rejected(valid_env: None) -> None:
    """Flipping a byte in the payload must invalidate the signature."""
    token = create_access_token(user_id=uuid.uuid4(), role=UserRole.CANDIDATE)
    head, payload, signature = token.split(".")

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{payload}x.{signature}")


def test_garbage_token_is_rejected(valid_env: None) -> None:
    """A non-JWT string must fail closed rather than raise something unhandled."""
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.jwt")


def test_token_with_unknown_role_is_rejected(valid_env: None) -> None:
    """A role outside the enum must not decode into an undefined authz state."""
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "SUPERADMIN", "exp": 9999999999},
        "a" * 32,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
