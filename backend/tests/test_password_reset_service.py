"""Password-reset service checks against a real, migrated Postgres (opt-in).

    uv run alembic upgrade head
    CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_password_reset_service.py
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.services.auth import (
    InvalidCredentials,
    InvalidResetToken,
    authenticate_user,
    create_password_reset_token,
    register_user,
    request_password_reset,
    reset_password,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)

_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
_OLD_PW = "hunter2hunter2"


class _SpySender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).timestamp()}@example.com"


async def _register(session, email: str):
    return await register_user(
        session, email=email, password=_OLD_PW,
        display_name=None, settings=get_settings(), email_sender=_SpySender(),
    )


async def test_request_password_reset_emails_an_existing_user() -> None:
    email = _unique_email("pwreq")
    spy = _SpySender()
    async with async_session_factory() as session:
        await _register(session, email)
        await request_password_reset(
            session, email=email, settings=get_settings(), email_sender=spy
        )
    assert spy.sent and spy.sent[0][0] == email


async def test_request_password_reset_is_silent_for_unknown_email() -> None:
    spy = _SpySender()
    async with async_session_factory() as session:
        # No account, no error, no email — avoids account enumeration.
        await request_password_reset(
            session, email="nobody@example.com", settings=get_settings(), email_sender=spy
        )
    assert spy.sent == []


async def test_reset_password_changes_the_password() -> None:
    email = _unique_email("pwchg")
    async with async_session_factory() as session:
        user = await _register(session, email)
        raw = await create_password_reset_token(session, user, now=_NOW)

        await reset_password(
            session, raw_token=raw, new_password="brand-new-pass", now=_NOW + timedelta(minutes=5)
        )

        with pytest.raises(InvalidCredentials):
            await authenticate_user(session, email=email, password=_OLD_PW)
        refreshed = await authenticate_user(session, email=email, password="brand-new-pass")
        assert refreshed.email == email


async def test_reset_token_is_single_use() -> None:
    email = _unique_email("pw1use")
    async with async_session_factory() as session:
        user = await _register(session, email)
        raw = await create_password_reset_token(session, user, now=_NOW)
        await reset_password(
            session, raw_token=raw, new_password="newpass123", now=_NOW + timedelta(minutes=1)
        )
        with pytest.raises(InvalidResetToken):
            await reset_password(
                session, raw_token=raw, new_password="another123", now=_NOW + timedelta(minutes=2)
            )


async def test_reset_password_rejects_expired_token() -> None:
    email = _unique_email("pwexp")
    async with async_session_factory() as session:
        user = await _register(session, email)
        raw = await create_password_reset_token(session, user, ttl_hours=1, now=_NOW)
        with pytest.raises(InvalidResetToken):
            await reset_password(
                session, raw_token=raw, new_password="newpass123", now=_NOW + timedelta(hours=2)
            )


async def test_reset_password_rejects_unknown_token() -> None:
    async with async_session_factory() as session:
        with pytest.raises(InvalidResetToken):
            await reset_password(session, raw_token="not-real", new_password="newpass123", now=_NOW)
