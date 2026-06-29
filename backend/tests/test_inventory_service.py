"""Allocation-model service checks against a real, migrated Postgres (opt-in)."""

import os
import uuid

import pytest
from sqlalchemy import select

from app.core.db import async_session_factory
from app.models.card import Card
from app.models.enums import DeckBoard, DeckFormat, LocationKind
from app.models.holding import Holding
from app.models.user import User
from app.services.inventory import (
    InsufficientQuantity,
    add_holding,
    create_deck,
    ensure_default_location,
    move_holding,
    set_deck_entry,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


async def _make_user(session) -> User:
    user = User(email=f"inv-{uuid.uuid4()}@example.com")
    session.add(user)
    await session.flush()
    return user


async def _make_card(session, name: str = "Sol Ring") -> Card:
    card = Card(scryfall_id=uuid.uuid4(), data={"id": str(uuid.uuid4()), "name": name})
    session.add(card)
    await session.flush()
    return card


async def _qty_at(session, location_id, card_id) -> int:
    holding = await session.scalar(
        select(Holding).where(Holding.location_id == location_id, Holding.card_id == card_id)
    )
    return holding.quantity if holding else 0


async def test_ensure_default_location_is_idempotent() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        first = await ensure_default_location(session, user)
        second = await ensure_default_location(session, user)
        assert first.id == second.id
        assert first.kind == LocationKind.STORAGE


async def test_add_holding_creates_then_increments_the_same_stack() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        loc = await ensure_default_location(session, user)

        await add_holding(session, location=loc, card_id=card.id, quantity=2)
        holding = await add_holding(session, location=loc, card_id=card.id, quantity=3)

        assert holding.quantity == 5


async def test_move_holding_transfers_quantity_between_locations() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)

        await add_holding(session, location=storage, card_id=card.id, quantity=3)
        await move_holding(
            session, from_location=storage, to_location=deck.location, card_id=card.id, quantity=2
        )

        assert await _qty_at(session, storage.id, card.id) == 1
        assert await _qty_at(session, deck.location_id, card.id) == 2


async def test_move_holding_rejects_insufficient_quantity() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH2", format=DeckFormat.COMMANDER)
        await add_holding(session, location=storage, card_id=card.id, quantity=1)

        with pytest.raises(InsufficientQuantity):
            await move_holding(
                session, from_location=storage, to_location=deck.location,
                card_id=card.id, quantity=2,
            )
        # Source quantity is untouched after a failed move.
        assert await _qty_at(session, storage.id, card.id) == 1


async def test_create_deck_makes_a_deck_kind_location() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        deck = await create_deck(session, user=user, name="My EDH", format=DeckFormat.COMMANDER)
        assert deck.location.kind == LocationKind.DECK
        assert deck.location.name == "My EDH"
        assert deck.format == DeckFormat.COMMANDER


async def test_set_deck_entry_upserts_desired_quantity() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        deck = await create_deck(session, user=user, name="EDH3", format=DeckFormat.COMMANDER)

        first = await set_deck_entry(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, desired_quantity=1
        )
        assert first.desired_quantity == 1
        second = await set_deck_entry(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, desired_quantity=4
        )
        assert second.desired_quantity == 4
        assert second.id == first.id
