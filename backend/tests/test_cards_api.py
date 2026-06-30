import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_scryfall_service
from app.core.db import async_session_factory
from app.main import app
from app.models.card import Card

_DB_TESTS = os.environ.get("CABBYCARDS_DB_TESTS") == "1"


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_requires_non_empty_query() -> None:
    # q has min_length=1, so an empty query is a 422 before any Scryfall call.
    client = TestClient(app)
    response = client.get("/cards/search", params={"q": ""})
    assert response.status_code == 422


def test_openapi_exposes_card_routes() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/cards/search" in paths
    assert "/cards/local-search" in paths
    assert "/cards/{scryfall_id}" in paths


# ---------------------------------------------------------------------------
# DB-gated: printings endpoint
# ---------------------------------------------------------------------------

async def _seed_two_printings() -> tuple[Card, list[Card]]:
    """Persist two cards sharing an oracle_id and return (first, [both])."""
    oracle_id = uuid.uuid4()
    async with async_session_factory() as session:
        card_a = Card(
            scryfall_id=uuid.uuid4(),
            oracle_id=oracle_id,
            data={"id": str(uuid.uuid4()), "name": "Lightning Bolt", "type_line": "Instant",
                  "color_identity": ["R"], "legalities": {}},
        )
        card_b = Card(
            scryfall_id=uuid.uuid4(),
            oracle_id=oracle_id,
            data={"id": str(uuid.uuid4()), "name": "Lightning Bolt", "type_line": "Instant",
                  "color_identity": ["R"], "legalities": {}},
        )
        session.add_all([card_a, card_b])
        await session.commit()
        await session.refresh(card_a)
        await session.refresh(card_b)
        return card_a, [card_a, card_b]


class _FakePrintingsScryfall:
    """Fake that returns a known card for get_card and two printings for list_printings."""

    def __init__(self, card: Card, printings: list[Card]) -> None:
        self._card = card
        self._printings = printings

    async def get_card(self, scryfall_id: uuid.UUID, **_kwargs: object) -> Card:
        return self._card

    async def list_printings(self, oracle_id: uuid.UUID) -> list[Card]:
        return self._printings


@pytest.fixture(autouse=True)
def _reset_overrides_cards():
    yield
    app.dependency_overrides.clear()


@pytest.mark.skipif(
    not _DB_TESTS, reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)"
)
async def test_card_printings_returns_all_printings() -> None:
    """GET /cards/{scryfall_id}/printings delegates to the service and returns all printings.

    See: tests/test_cards_api.py
    """
    card, printings = await _seed_two_printings()
    fake = _FakePrintingsScryfall(card, printings)
    app.dependency_overrides[get_scryfall_service] = lambda: fake

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/cards/{card.scryfall_id}/printings")

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
    assert all(r["name"] == "Lightning Bolt" for r in results)
