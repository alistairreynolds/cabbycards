"""Deck HTTP endpoint checks against a real, migrated Postgres (opt-in)."""

import os
import uuid

import httpx
import pytest

from app.api.deps import get_scryfall_service
from app.core.db import async_session_factory
from app.core.security import create_access_token
from app.main import app
from app.models.card import Card
from app.models.user import User

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


class _FakeScryfall:
    def __init__(self, card: Card) -> None:
        self._card = card

    async def get_card(self, scryfall_id: uuid.UUID, **_kwargs: object) -> Card:
        return self._card


async def _seed_user_and_card() -> tuple[User, Card]:
    async with async_session_factory() as session:
        user = User(email=f"deckapi-{uuid.uuid4()}@example.com")
        card = Card(
            scryfall_id=uuid.uuid4(),
            oracle_id=uuid.uuid4(),
            data={"id": str(uuid.uuid4()), "name": "Sol Ring", "type_line": "Artifact",
                  "color_identity": [], "legalities": {"commander": "legal"}},
        )
        session.add_all([user, card])
        await session.commit()
        await session.refresh(user)
        await session.refresh(card)
        return user, card


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


async def test_decks_require_auth() -> None:
    async with _client() as ac:
        assert (await ac.get("/decks")).status_code == 401


async def test_create_then_list_and_get_deck() -> None:
    user, _ = await _seed_user_and_card()
    headers = _auth(user)
    async with _client() as ac:
        created = await ac.post("/decks", headers=headers, json={"name": "My EDH"})
        assert created.status_code == 201
        deck_id = created.json()["id"]

        listed = (await ac.get("/decks", headers=headers)).json()
        assert any(d["id"] == deck_id for d in listed)

        view = (await ac.get(f"/decks/{deck_id}", headers=headers)).json()
        assert view["name"] == "My EDH"
        assert view["cards"] == []


async def test_add_card_appears_in_deck_view_as_missing() -> None:
    user, card = await _seed_user_and_card()
    app.dependency_overrides[get_scryfall_service] = lambda: _FakeScryfall(card)
    headers = _auth(user)
    async with _client() as ac:
        deck_id = (await ac.post("/decks", headers=headers, json={"name": "EDH"})).json()["id"]
        added = await ac.post(
            f"/decks/{deck_id}/cards",
            headers=headers,
            json={"scryfall_id": str(uuid.uuid4()), "quantity": 1},
        )
        assert added.status_code == 201
        view = (await ac.get(f"/decks/{deck_id}", headers=headers)).json()
    assert view["cards"][0]["card"]["name"] == "Sol Ring"
    assert view["cards"][0]["missing_quantity"] == 1


async def test_get_other_users_deck_is_404() -> None:
    user, _ = await _seed_user_and_card()
    other, _ = await _seed_user_and_card()
    async with _client() as ac:
        deck_id = (
            await ac.post("/decks", headers=_auth(user), json={"name": "Mine"})
        ).json()["id"]
        resp = await ac.get(f"/decks/{deck_id}", headers=_auth(other))
    assert resp.status_code == 404


async def test_delete_deck() -> None:
    user, _ = await _seed_user_and_card()
    headers = _auth(user)
    async with _client() as ac:
        deck_id = (await ac.post("/decks", headers=headers, json={"name": "Temp"})).json()["id"]
        deleted = await ac.delete(f"/decks/{deck_id}", headers=headers)
        assert deleted.status_code == 204
        assert (await ac.get(f"/decks/{deck_id}", headers=headers)).status_code == 404
