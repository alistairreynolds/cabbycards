"""Auth service checks against a real, migrated Postgres (opt-in).

    uv run alembic upgrade head
    CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_auth_service.py
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.security import verify_password
from app.models.auth_identity import AuthIdentity
from app.models.enums import AuthIdentityType
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidVerificationToken,
    authenticate_user,
    create_verification_token,
    register_user,
    verify_email_token,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)

_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


class _SpySender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _unique_email(prefix: str) -> str:
    # Each test run gets a fresh address so the shared verify DB stays isolated.
    return f"{prefix}-{datetime.now(UTC).timestamp()}@example.com"


async def test_register_creates_user_password_identity_and_sends_email() -> None:
    email = _unique_email("reg")
    spy = _SpySender()
    async with async_session_factory() as session:
        user = await register_user(
            session,
            email=email,
            password="hunter2hunter2",
            display_name="Cabby",
            settings=get_settings(),
            email_sender=spy,
        )

        assert user.email == email
        assert user.email_verified is False

        identity = await session.scalar(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id,
                AuthIdentity.type == AuthIdentityType.PASSWORD,
            )
        )
        assert identity is not None
        assert verify_password("hunter2hunter2", identity.password_hash) is True

    assert spy.sent and spy.sent[0][0] == email


async def test_register_lowercases_email() -> None:
    email = _unique_email("MixedCase").upper()
    async with async_session_factory() as session:
        user = await register_user(
            session,
            email=email,
            password="hunter2hunter2",
            display_name=None,
            settings=get_settings(),
            email_sender=_SpySender(),
        )
        assert user.email == email.lower()


async def test_register_duplicate_email_raises() -> None:
    email = _unique_email("dupe")
    async with async_session_factory() as session:
        await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )
        with pytest.raises(EmailAlreadyRegistered):
            await register_user(
                session, email=email, password="other-password",
                display_name=None, settings=get_settings(), email_sender=_SpySender(),
            )


async def test_authenticate_succeeds_with_correct_password() -> None:
    email = _unique_email("auth")
    async with async_session_factory() as session:
        await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )
        user = await authenticate_user(session, email=email.upper(), password="hunter2hunter2")
        assert user.email == email


async def test_authenticate_wrong_password_raises() -> None:
    email = _unique_email("wrongpw")
    async with async_session_factory() as session:
        await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )
        with pytest.raises(InvalidCredentials):
            await authenticate_user(session, email=email, password="nope")


async def test_authenticate_unknown_email_raises() -> None:
    async with async_session_factory() as session:
        with pytest.raises(InvalidCredentials):
            await authenticate_user(session, email="nobody@example.com", password="whatever")


async def test_verify_email_marks_verified_and_consumes_token() -> None:
    email = _unique_email("verify")
    async with async_session_factory() as session:
        user = await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )
        raw = await create_verification_token(session, user, now=_NOW)

        verified = await verify_email_token(session, raw, now=_NOW + timedelta(minutes=5))
        assert verified.email_verified is True

        # Single-use: the same token cannot be redeemed twice.
        with pytest.raises(InvalidVerificationToken):
            await verify_email_token(session, raw, now=_NOW + timedelta(minutes=6))


async def test_verify_email_rejects_expired_token() -> None:
    email = _unique_email("expired")
    async with async_session_factory() as session:
        user = await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )
        raw = await create_verification_token(session, user, ttl_hours=24, now=_NOW)
        with pytest.raises(InvalidVerificationToken):
            await verify_email_token(session, raw, now=_NOW + timedelta(hours=25))


async def test_verify_email_rejects_unknown_token() -> None:
    async with async_session_factory() as session:
        with pytest.raises(InvalidVerificationToken):
            await verify_email_token(session, "not-a-real-token", now=_NOW)
