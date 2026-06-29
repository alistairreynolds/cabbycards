"""Password-reset HTTP endpoint checks against a real, migrated Postgres (opt-in)."""

import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.api.deps import get_email_sender, get_turnstile_verifier
from app.core.db import async_session_factory
from app.main import app
from app.models.user import User
from app.services.auth import create_password_reset_token, register_user

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


class _SpySender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _turnstile_returning(result: bool) -> Callable[[], Callable[[str], Awaitable[bool]]]:
    async def _verify(_token: str) -> bool:
        return result

    return lambda: _verify


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).timestamp()}@example.com"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


async def _seed_user(email: str) -> None:
    from app.core.config import get_settings

    async with async_session_factory() as session:
        await register_user(
            session, email=email, password="hunter2hunter2",
            display_name=None, settings=get_settings(), email_sender=_SpySender(),
        )


async def test_forgot_password_returns_202_for_unknown_email() -> None:
    app.dependency_overrides[get_turnstile_verifier] = _turnstile_returning(True)
    app.dependency_overrides[get_email_sender] = lambda: _SpySender()

    async with _client() as ac:
        response = await ac.post(
            "/auth/forgot-password",
            json={"email": "ghost@example.com", "turnstile_token": "ok"},
        )
    # 202 regardless of existence — no account enumeration.
    assert response.status_code == 202


async def test_forgot_password_emails_a_known_user() -> None:
    spy = _SpySender()
    app.dependency_overrides[get_turnstile_verifier] = _turnstile_returning(True)
    app.dependency_overrides[get_email_sender] = lambda: spy
    email = _unique_email("forgot")
    await _seed_user(email)

    async with _client() as ac:
        response = await ac.post(
            "/auth/forgot-password", json={"email": email, "turnstile_token": "ok"}
        )

    assert response.status_code == 202
    assert any(sent[0] == email for sent in spy.sent)


async def test_forgot_password_fails_bot_check_with_403() -> None:
    app.dependency_overrides[get_turnstile_verifier] = _turnstile_returning(False)
    app.dependency_overrides[get_email_sender] = lambda: _SpySender()

    async with _client() as ac:
        response = await ac.post(
            "/auth/forgot-password",
            json={"email": "x@example.com", "turnstile_token": "x"},
        )
    assert response.status_code == 403


async def test_reset_password_with_valid_token_then_login_with_new_password() -> None:
    email = _unique_email("reset")
    await _seed_user(email)
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        raw_token = await create_password_reset_token(session, user)

    async with _client() as ac:
        reset = await ac.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "brand-new-pass"},
        )
        assert reset.status_code == 200
        assert reset.json()["access_token"]

        new_login = await ac.post(
            "/auth/login", json={"email": email, "password": "brand-new-pass"}
        )
        old_login = await ac.post(
            "/auth/login", json={"email": email, "password": "hunter2hunter2"}
        )

    assert new_login.status_code == 200
    assert old_login.status_code == 401


async def test_reset_password_rejects_bad_token_with_400() -> None:
    async with _client() as ac:
        response = await ac.post(
            "/auth/reset-password",
            json={"token": "not-a-real-token", "new_password": "whatever123"},
        )
    assert response.status_code == 400
