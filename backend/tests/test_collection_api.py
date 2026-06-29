"""Collection HTTP endpoint checks against a real, migrated Postgres (opt-in)."""

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
    """Stands in for ScryfallService.get_card — returns a pre-seeded card, no network."""

    def __init__(self, card: Card) -> None:
        self._card = card

    async def get_card(self, scryfall_id: uuid.UUID, **_kwargs: object) -> Card:
        return self._card


async def _seed_user_and_card() -> tuple[User, Card]:
    async with async_session_factory() as session:
        user = User(email=f"col-{uuid.uuid4()}@example.com")
        card = Card(scryfall_id=uuid.uuid4(), data={"id": str(uuid.uuid4()), "name": "Sol Ring"})
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


async def test_collection_requires_auth() -> None:
    async with _client() as ac:
        assert (await ac.get("/collection")).status_code == 401


async def test_locations_includes_default_unsorted() -> None:
    user, _ = await _seed_user_and_card()
    async with _client() as ac:
        response = await ac.get("/collection/locations", headers=_auth(user))
    assert response.status_code == 200
    names = [loc["name"] for loc in response.json()]
    assert "Unsorted" in names


async def test_add_card_then_it_appears_in_the_collection() -> None:
    user, card = await _seed_user_and_card()
    app.dependency_overrides[get_scryfall_service] = lambda: _FakeScryfall(card)
    headers = _auth(user)

    async with _client() as ac:
        unsorted = (await ac.get("/collection/locations", headers=headers)).json()[0]
        added = await ac.post(
            "/collection/add",
            headers=headers,
            json={"scryfall_id": str(uuid.uuid4()), "location_id": unsorted["id"], "quantity": 2},
        )
        assert added.status_code == 201

        items = (await ac.get("/collection", headers=headers)).json()

    assert len(items) == 1
    assert items[0]["quantity"] == 2
    assert items[0]["card"]["name"] == "Sol Ring"
    assert items[0]["location_id"] == unsorted["id"]


async def test_move_card_between_locations() -> None:
    user, card = await _seed_user_and_card()
    app.dependency_overrides[get_scryfall_service] = lambda: _FakeScryfall(card)
    headers = _auth(user)

    async with _client() as ac:
        unsorted = (await ac.get("/collection/locations", headers=headers)).json()[0]
        binder = (
            await ac.post("/collection/locations", headers=headers, json={"name": "Binder A"})
        ).json()
        await ac.post(
            "/collection/add",
            headers=headers,
            json={"scryfall_id": str(uuid.uuid4()), "location_id": unsorted["id"], "quantity": 3},
        )

        moved = await ac.post(
            "/collection/move",
            headers=headers,
            json={
                "card_id": card.id,
                "from_location_id": unsorted["id"],
                "to_location_id": binder["id"],
                "quantity": 2,
            },
        )
        assert moved.status_code == 200

        items = (await ac.get("/collection", headers=headers)).json()

    by_location = {item["location_id"]: item["quantity"] for item in items}
    assert by_location[unsorted["id"]] == 1
    assert by_location[binder["id"]] == 2


async def test_move_more_than_owned_is_rejected() -> None:
    user, card = await _seed_user_and_card()
    app.dependency_overrides[get_scryfall_service] = lambda: _FakeScryfall(card)
    headers = _auth(user)

    async with _client() as ac:
        unsorted = (await ac.get("/collection/locations", headers=headers)).json()[0]
        binder = (
            await ac.post("/collection/locations", headers=headers, json={"name": "Binder B"})
        ).json()
        await ac.post(
            "/collection/add",
            headers=headers,
            json={"scryfall_id": str(uuid.uuid4()), "location_id": unsorted["id"], "quantity": 1},
        )
        moved = await ac.post(
            "/collection/move",
            headers=headers,
            json={
                "card_id": card.id,
                "from_location_id": unsorted["id"],
                "to_location_id": binder["id"],
                "quantity": 5,
            },
        )
    assert moved.status_code == 400


async def test_delete_holding() -> None:
    user, card = await _seed_user_and_card()
    app.dependency_overrides[get_scryfall_service] = lambda: _FakeScryfall(card)
    headers = _auth(user)

    async with _client() as ac:
        unsorted = (await ac.get("/collection/locations", headers=headers)).json()[0]
        await ac.post(
            "/collection/add",
            headers=headers,
            json={"scryfall_id": str(uuid.uuid4()), "location_id": unsorted["id"], "quantity": 1},
        )
        holding = (await ac.get("/collection", headers=headers)).json()[0]
        deleted = await ac.delete(f"/collection/holdings/{holding['id']}", headers=headers)
        assert deleted.status_code == 204

        remaining = (await ac.get("/collection", headers=headers)).json()

    assert remaining == []
