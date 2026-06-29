"""End-to-end checks against a real, migrated Postgres.

Skipped unless CABBYCARDS_DB_TESTS=1. Point DATABASE_URL at a migrated database
(docker compose, or a local throwaway DB) and run:

    uv run alembic upgrade head
    CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_integration_db.py
"""

import os
import uuid

import httpx
import pytest
from sqlalchemy import func

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.services.card_search import DEFAULT_SIMILARITY_THRESHOLD, search_cached_cards
from app.services.scryfall import ScryfallService

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


def _fake_card(name: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "oracle_id": str(uuid.uuid4()),
        "name": name,
        "type_line": "Artifact",
    }


async def _ingest_cards(session, names: list[str]) -> None:
    """Persist fake cards by reusing the service's real upsert/ingest path."""
    offline_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, json={})),
        base_url="https://api.scryfall.test",
    )
    async with ScryfallService(session, settings=get_settings(), client=offline_client) as service:
        for name in names:
            await service._ingest(_fake_card(name))


async def test_ingest_populates_generated_name_and_fuzzy_search_finds_it() -> None:
    payload = _fake_card("Sol Ring")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.scryfall.test"
    )

    async with async_session_factory() as session:
        async with ScryfallService(session, settings=get_settings(), client=client) as service:
            card = await service.get_card(uuid.UUID(payload["id"]))
            # The generated column must have been populated from the JSONB blob.
            assert card.name == "Sol Ring"

        # A fuzzy, typo'd query should still surface the card via pg_trgm.
        hits = await search_cached_cards(session, "sol rng")
        assert any(hit.scryfall_id == uuid.UUID(payload["id"]) for hit in hits)


async def test_exact_match_ranks_above_fuzzy() -> None:
    async with async_session_factory() as session:
        await _ingest_cards(session, ["Lightning Bolt", "Lightning Helix", "Boltwood"])

        hits = await search_cached_cards(session, "Lightning Bolt")

        # The exact name must come first, ahead of any fuzzy near-matches.
        assert hits[0].name == "Lightning Bolt"


async def test_prefix_match_surfaces_below_fuzzy_threshold() -> None:
    async with async_session_factory() as session:
        await _ingest_cards(session, ["Lightning Bolt", "Lightning Helix"])

        # "li" is far too short to clear the trigram similarity threshold, so a
        # pure-fuzzy search would drop these. The prefix tier must still find them.
        similarity = await session.scalar(func.similarity("Lightning Bolt", "li"))
        assert similarity < DEFAULT_SIMILARITY_THRESHOLD

        names = {hit.name for hit in await search_cached_cards(session, "li")}
        assert {"Lightning Bolt", "Lightning Helix"} <= names
