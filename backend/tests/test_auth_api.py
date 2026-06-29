"""Auth HTTP endpoint checks against a real, migrated Postgres (opt-in).

    uv run alembic upgrade head
    CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_auth_api.py
"""

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
from app.services.auth import create_verification_token

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


def _allow_bot_check(spy: _SpySender) -> None:
    app.dependency_overrides[get_turnstile_verifier] = _turnstile_returning(True)
    app.dependency_overrides[get_email_sender] = lambda: spy


async def test_register_logs_in_and_me_returns_the_user() -> None:
    spy = _SpySender()
    _allow_bot_check(spy)
    email = _unique_email("api-reg")

    async with _client() as ac:
        registered = await ac.post(
            "/auth/register",
            json={"email": email, "password": "hunter2hunter2", "turnstile_token": "ok"},
        )
        assert registered.status_code == 201
        token = registered.json()["access_token"]

        me = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["email_verified"] is False
    assert spy.sent  # a verification email was queued


async def test_register_fails_bot_check_with_403() -> None:
    app.dependency_overrides[get_turnstile_verifier] = _turnstile_returning(False)
    app.dependency_overrides[get_email_sender] = lambda: _SpySender()

    async with _client() as ac:
        response = await ac.post(
            "/auth/register",
            json={
                "email": _unique_email("api-bot"),
                "password": "hunter2hunter2",
                "turnstile_token": "x",
            },
        )
    assert response.status_code == 403


async def test_register_duplicate_email_returns_409() -> None:
    _allow_bot_check(_SpySender())
    email = _unique_email("api-dupe")
    payload = {"email": email, "password": "hunter2hunter2", "turnstile_token": "ok"}

    async with _client() as ac:
        first = await ac.post("/auth/register", json=payload)
        second = await ac.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_login_succeeds_then_rejects_wrong_password() -> None:
    _allow_bot_check(_SpySender())
    email = _unique_email("api-login")

    async with _client() as ac:
        await ac.post(
            "/auth/register",
            json={"email": email, "password": "hunter2hunter2", "turnstile_token": "ok"},
        )
        ok = await ac.post("/auth/login", json={"email": email, "password": "hunter2hunter2"})
        bad = await ac.post("/auth/login", json={"email": email, "password": "wrong-one"})

    assert ok.status_code == 200
    assert ok.json()["access_token"]
    assert bad.status_code == 401


async def test_me_without_token_is_401() -> None:
    async with _client() as ac:
        response = await ac.get("/auth/me")
    assert response.status_code == 401


async def test_verify_email_endpoint_marks_verified() -> None:
    _allow_bot_check(_SpySender())
    email = _unique_email("api-verify")

    async with _client() as ac:
        await ac.post(
            "/auth/register",
            json={"email": email, "password": "hunter2hunter2", "turnstile_token": "ok"},
        )

    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        raw_token = await create_verification_token(session, user)

    async with _client() as ac:
        response = await ac.post("/auth/verify-email", json={"token": raw_token})

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
