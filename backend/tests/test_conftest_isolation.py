"""Proves the _clean_db fixture isolates DB-integration tests (opt-in)."""

import os
import uuid

import pytest
from sqlalchemy import func, select

from app.core.db import async_session_factory
from app.models.user import User

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


async def _user_count() -> int:
    async with async_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(User))


async def test_seeds_a_user() -> None:
    # The fixture truncates first, so we start empty even after other tests ran.
    assert await _user_count() == 0
    async with async_session_factory() as session:
        session.add(User(email=f"isolation-{uuid.uuid4()}@example.com"))
        await session.commit()
    assert await _user_count() == 1


async def test_previous_seed_was_truncated() -> None:
    # If isolation works, the user seeded above is gone before this test runs.
    assert await _user_count() == 0
