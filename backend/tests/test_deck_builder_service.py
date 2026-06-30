"""deck_builder DB orchestration against a real, migrated Postgres (opt-in)."""

import os
import uuid

import pytest
from sqlalchemy import select

from app.core.db import async_session_factory
from app.models.card import Card
from app.models.enums import DeckBoard, DeckFormat
from app.models.holding import Holding
from app.models.user import User
from app.services.deck_builder import (
    add_card_to_deck,
    build_deck_view,
    delete_deck,
    remove_card_from_deck,
)
from app.services.inventory import (
    add_holding,
    create_deck,
    create_storage_location,
    ensure_default_location,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("CABBYCARDS_DB_TESTS") != "1",
    reason="DB integration tests are opt-in (set CABBYCARDS_DB_TESTS=1)",
)


async def _make_user(session) -> User:
    user = User(email=f"deck-{uuid.uuid4()}@example.com")
    session.add(user)
    await session.flush()
    return user


async def _make_card(session, *, name="Sol Ring", oracle=None) -> Card:
    card = Card(
        scryfall_id=uuid.uuid4(),
        oracle_id=oracle or uuid.uuid4(),
        data={"id": str(uuid.uuid4()), "name": name, "type_line": "Artifact",
              "color_identity": [], "legalities": {"commander": "legal"}},
    )
    session.add(card)
    await session.flush()
    return card


async def _qty_at(session, location_id, card_id) -> int:
    holding = await session.scalar(
        select(Holding).where(Holding.location_id == location_id, Holding.card_id == card_id)
    )
    return holding.quantity if holding else 0


async def test_add_card_owned_auto_allocates_from_storage() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await add_holding(session, location=storage, card_id=card.id, quantity=1)

        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )

        assert await _qty_at(session, deck.location_id, card.id) == 1
        assert await _qty_at(session, storage.id, card.id) == 0


async def test_add_card_not_owned_is_entry_only() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)

        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )

        assert await _qty_at(session, deck.location_id, card.id) == 0
        view = await build_deck_view(session, deck=deck)
        row = next(r for r in view["cards"] if r["card"].id == card.id)
        assert row["desired_quantity"] == 1
        assert row["missing_quantity"] == 1


async def test_add_card_partial_ownership_allocates_what_it_can() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await add_holding(session, location=storage, card_id=card.id, quantity=1)

        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=3
        )

        assert await _qty_at(session, deck.location_id, card.id) == 1
        view = await build_deck_view(session, deck=deck)
        row = next(r for r in view["cards"] if r["card"].id == card.id)
        assert row["desired_quantity"] == 3
        assert row["allocated_quantity"] == 1
        assert row["missing_quantity"] == 2


async def test_add_card_allocates_from_a_non_default_storage_location() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        await ensure_default_location(session, user)  # Unsorted exists but is empty
        binder = await create_storage_location(session, user, "Binder A")
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await add_holding(session, location=binder, card_id=card.id, quantity=1)

        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )

        assert await _qty_at(session, deck.location_id, card.id) == 1
        assert await _qty_at(session, binder.id, card.id) == 0


async def test_owned_elsewhere_counts_against_missing_oracle_level() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        oracle = uuid.uuid4()
        picked = await _make_card(session, name="Sol Ring", oracle=oracle)
        other_printing = await _make_card(session, name="Sol Ring", oracle=oracle)
        binder = await create_storage_location(session, user, "Binder")
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await ensure_default_location(session, user)
        # Own a *different* printing in a binder; add the picked printing entry-only.
        await add_holding(session, location=binder, card_id=other_printing.id, quantity=1)

        await add_card_to_deck(
            session, deck=deck, card_id=picked.id, board=DeckBoard.MAIN, quantity=1
        )

        view = await build_deck_view(session, deck=deck)
        row = next(r for r in view["cards"] if r["card"].id == picked.id)
        assert row["owned_elsewhere_quantity"] == 1
        assert row["missing_quantity"] == 0  # owned (other printing) → not on the wantlist


async def test_remove_card_deallocates_back_to_unsorted() -> None:
    async with async_session_factory() as session:
        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await add_holding(session, location=storage, card_id=card.id, quantity=1)
        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )

        await remove_card_from_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )

        assert await _qty_at(session, deck.location_id, card.id) == 0
        assert await _qty_at(session, storage.id, card.id) == 1


async def test_delete_deck_relocates_holdings_and_removes_deck() -> None:
    async with async_session_factory() as session:
        from app.models.deck import Deck

        user = await _make_user(session)
        card = await _make_card(session)
        storage = await ensure_default_location(session, user)
        deck = await create_deck(session, user=user, name="EDH", format=DeckFormat.COMMANDER)
        await add_holding(session, location=storage, card_id=card.id, quantity=1)
        await add_card_to_deck(
            session, deck=deck, card_id=card.id, board=DeckBoard.MAIN, quantity=1
        )
        deck_location_id = deck.location_id

        await delete_deck(session, deck=deck)

        assert await session.get(Deck, deck_location_id) is None
        assert await _qty_at(session, storage.id, card.id) == 1
