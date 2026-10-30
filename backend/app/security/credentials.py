import hashlib
import re
import secrets
from typing import Literal

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

# Explicit RFC 9106 low-memory profile; tune against deployment hardware later.
PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
# Process-local dummy uses the same work factor; never an account credential.
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        result = PASSWORD_HASHER.verify(encoded or DUMMY_HASH, password)
    except VerificationError, InvalidHashError:
        return False
    return bool(encoded) and result


def new_token() -> str:
    return secrets.token_urlsafe(32)


def valid_token(value: str) -> bool:
    return TOKEN_PATTERN.fullmatch(value) is not None


def token_digest(value: str, purpose: Literal["session", "verification"]) -> str:
    return hashlib.sha256(f"{purpose}:{value}".encode("ascii")).hexdigest()
