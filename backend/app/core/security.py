import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import get_settings

_hasher = PasswordHasher()


class TokenError(Exception):
    """Raised when a session JWT is invalid, expired, or malformed."""


def hash_password(password: str) -> str:
    """Hash a password with Argon2id (salt is generated and embedded).

    See: tests/test_security.py
    """
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Return whether the password matches the stored Argon2 hash.

    See: tests/test_security.py
    """
    try:
        return _hasher.verify(hashed, password)
    except Argon2Error:
        return False


def create_access_token(subject: str, *, expires_minutes: int | None = None) -> str:
    """Issue a signed session JWT for the given subject (user id).

    See: tests/test_security.py
    """
    settings = get_settings()
    minutes = settings.jwt_expiry_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Verify a session JWT and return its subject, or raise TokenError.

    See: tests/test_security.py
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token missing subject")
    return subject


def hash_token(raw: str) -> str:
    """Hash an opaque token (e.g. email verification) for at-rest storage.

    See: tests/test_security.py
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_verification_token() -> tuple[str, str]:
    """Generate a (raw, hash) pair: email the raw, store only the hash.

    See: tests/test_security.py
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
