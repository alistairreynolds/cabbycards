import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import text

# Load the documented example config so tests use the same values as .env.example
# rather than anything hardcoded in code. override=False means a real env var
# (e.g. an integration DATABASE_URL exported before pytest) still wins.
_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
load_dotenv(_ENV_EXAMPLE, override=False)

_DB_TESTS_ENABLED = os.environ.get("CABBYCARDS_DB_TESTS") == "1"


@pytest.fixture(autouse=True)
async def _clean_db():
    """Truncate every table before each DB-integration test for isolation.

    The opt-in DB suite shares one Postgres with no rollback, so rows seeded by
    one test used to leak into the next (a shared name could collide). This wipes
    all model tables — RESTART IDENTITY resets serials, CASCADE clears dependents
    — leaving each test a clean slate. A no-op unless CABBYCARDS_DB_TESTS=1, so
    hermetic runs never touch the database.

    See: tests/test_conftest_isolation.py
    """
    if not _DB_TESTS_ENABLED:
        yield
        return

    # Imported lazily so hermetic runs never require a reachable database.
    from app.core.db import engine
    from app.models.base import Base

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    yield
