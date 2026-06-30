# ALI-12 Deck Building Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a commander-first deck builder — create decks, set a commander, add cards filtered by colour identity + format legality, and auto-allocate owned physical copies into the deck.

**Architecture:** A new `deck_builder` service orchestrates the existing ALI-18 primitives (`set_deck_entry`, `move_holding`) over the existing schema (no migration). A `decks` API router exposes deck CRUD + contents and a computed deck-view read model. Scryfall search gains filter-syntax helpers. The Vue SPA gets a decks store, a list view, an Archidekt-style builder view, and a shared `PrintingSelector`.

**Tech Stack:** Python ≥3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, PostgreSQL, pytest, httpx MockTransport; Vue 3 + TS + Pinia + Vue Router + Tailwind v4 + Vitest.

## Global Constraints

- British English in identifiers/comments (`colour`, not `color`) — except where mirroring Scryfall's JSON keys (`color_identity` stays as Scryfall spells it).
- Early returns over deep nesting; no nested ternaries.
- Private methods/attributes prefixed `_`.
- Comments explain why, not what.
- Every function has a test and references it with a `See: <test file>` line in its docstring.
- Reuse before rebuild (AHA) — prefer existing helpers (`move_holding`, `set_deck_entry`, `ensure_default_location`, `ScryfallService.search`).
- Native PG enums store values not names (`pg_enum` already handles this).
- All DB access is async SQLAlchemy 2.0; sessions via `Depends(get_session)`.
- Backend commands run under `uv` from `backend/` (`uv run pytest`, `uv run ruff check .`). Frontend under `npm` from `frontend/` (`npm run test`, `npm run lint`).
- DB-backed tests are opt-in via `CABBYCARDS_DB_TESTS=1` and `pytestmark = pytest.mark.skipif(...)`. Pure-function / MockTransport / Vitest tests always run.
- Deck ownership is via `locations.user_id`; a deck's primary key is its `location_id`.
- Delivery: one PR on branch `madcabbage/ali-12-deck-building-commander-colour-identity-format-legality`, split into the commits below. Do not push without asking.

---

## File Structure

**Backend**
- Create `app/services/deck_builder.py` — validation (pure) + deck orchestration (DB).
- Create `app/api/routes/decks.py` — decks router.
- Create `app/schemas/deck.py` — deck request/response schemas.
- Modify `app/api/deps.py` — add `get_owned_deck`.
- Modify `app/services/scryfall.py` — add `build_scryfall_query` (pure) + `search_cards` + `list_printings`.
- Modify `app/api/routes/cards.py` — add `/cards/{scryfall_id}/printings`.
- Modify `app/main.py` — register the decks router.
- Create tests: `tests/test_deck_validation.py`, `tests/test_deck_builder_service.py`, `tests/test_decks_api.py`, `tests/test_scryfall_query.py`; extend `tests/test_scryfall_service.py`.

**Frontend**
- Create `src/stores/decks.ts` (+ `src/stores/decks.spec.ts`).
- Create `src/views/DecksView.vue`, `src/views/DeckBuilderView.vue`.
- Create `src/components/PrintingSelector.vue` (+ `src/components/PrintingSelector.spec.ts`).
- Modify `src/router/index.ts` — add `/decks` and `/decks/:id`.
- Modify `src/App.vue` — Collection ⇄ Decks nav.
- Modify `src/components/AddCardSearch.vue` — optional deck-filtered search endpoint.

---

## COMMIT 1 — deck_builder service (validation + orchestration)

### Task 1: `deck_violations` pure validation function

**Files:**
- Create: `backend/app/services/deck_builder.py`
- Test: `backend/tests/test_deck_validation.py`

**Interfaces:**
- Produces: `deck_violations(rows, *, format, commander_identity, has_commander) -> dict[str, object]` where `rows` is a list of dicts each `{"name": str, "color_identity": list[str], "type_line": str, "legalities": dict[str, str], "desired_quantity": int, "board": str}`; `commander_identity` is a `set[str]` of single-letter colours; returns `{"cards": {name: [codes]}, "deck": [codes]}`.
- Codes: per-card `off_colour_identity`, `not_format_legal`; deck-level `no_commander`, `wrong_size`, `singleton_violation`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_deck_validation.py
"""Pure deck-legality checks — no DB, always run."""

from app.models.enums import DeckBoard, DeckFormat
from app.services.deck_builder import deck_violations


def _card(name, *, identity=(), type_line="Creature", legal="legal", qty=1, board=DeckBoard.MAIN):
    return {
        "name": name,
        "color_identity": list(identity),
        "type_line": type_line,
        "legalities": {"commander": legal},
        "desired_quantity": qty,
        "board": board.value,
    }


def test_off_colour_identity_is_flagged() -> None:
    rows = [_card("Lightning Bolt", identity=("R",))]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U", "W"}, has_commander=True
    )
    assert "off_colour_identity" in result["cards"]["Lightning Bolt"]


def test_in_identity_card_is_clean() -> None:
    rows = [_card("Counterspell", identity=("U",))]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U", "W"}, has_commander=True
    )
    assert result["cards"].get("Counterspell", []) == []


def test_not_format_legal_is_flagged() -> None:
    rows = [_card("Black Lotus", legal="banned")]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=True
    )
    assert "not_format_legal" in result["cards"]["Black Lotus"]


def test_singleton_violation_for_non_basic_duplicate() -> None:
    rows = [_card("Sol Ring", identity=(), type_line="Artifact", qty=2)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=True
    )
    assert "singleton_violation" in result["deck"]


def test_basic_land_duplicates_are_allowed() -> None:
    rows = [_card("Island", identity=("U",), type_line="Basic Land — Island", qty=30)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U"}, has_commander=True
    )
    assert "singleton_violation" not in result["deck"]


def test_no_commander_and_wrong_size_for_commander_deck() -> None:
    rows = [_card("Island", identity=("U",), type_line="Basic Land", qty=10)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=False
    )
    assert "no_commander" in result["deck"]
    assert "wrong_size" in result["deck"]


def test_standard_format_skips_commander_only_rules() -> None:
    rows = [_card("Llanowar Elves", identity=("G",), legal="legal", qty=4)]
    rows[0]["legalities"] = {"standard": "legal"}
    result = deck_violations(
        rows, format=DeckFormat.STANDARD, commander_identity=set(), has_commander=False
    )
    assert result["deck"] == []
    assert result["cards"].get("Llanowar Elves", []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_deck_validation.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'deck_violations'`.

- [ ] **Step 3: Implement the pure validation**

```python
# backend/app/services/deck_builder.py
"""Deck building: legality validation (pure) + allocation orchestration (DB).

Sits on top of the ALI-18 inventory primitives — it never writes holdings or
entries directly, it calls move_holding / set_deck_entry.
"""

from app.models.enums import DeckFormat

# Formats where the deck is a singleton 100-card (incl. commander) list.
_SINGLETON_FORMATS = {DeckFormat.COMMANDER, DeckFormat.BRAWL}
# Scryfall legality states that count as playable.
_LEGAL_STATES = {"legal", "restricted"}
# Boards that count toward the singleton/size rules (the actual deck, not maybe/side).
_COUNTED_BOARDS = {"main", "command"}
_BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _is_basic_land(name: str, type_line: str) -> bool:
    # Basics (and snow basics) are exempt from the singleton rule.
    return name in _BASIC_LAND_NAMES or "Basic" in type_line


def _card_codes(
    row: dict, *, format: DeckFormat, commander_identity: set[str], has_commander: bool
) -> list[str]:
    codes: list[str] = []
    legal_state = row["legalities"].get(format.value)
    if legal_state not in _LEGAL_STATES:
        codes.append("not_format_legal")
    if has_commander and not set(row["color_identity"]).issubset(commander_identity):
        codes.append("off_colour_identity")
    return codes


def deck_violations(
    rows: list[dict],
    *,
    format: DeckFormat,
    commander_identity: set[str],
    has_commander: bool,
) -> dict[str, object]:
    """Return per-card and deck-level legality violation codes.

    Pure — takes plain card facts, no DB. ``rows`` carry name, color_identity,
    type_line, legalities, desired_quantity and board. Deck-level singleton/size
    rules apply only to singleton formats (Commander/Brawl).

    See: tests/test_deck_validation.py
    """
    card_codes = {
        row["name"]: _card_codes(
            row,
            format=format,
            commander_identity=commander_identity,
            has_commander=has_commander,
        )
        for row in rows
    }

    deck_codes: list[str] = []
    if format not in _SINGLETON_FORMATS:
        return {"cards": card_codes, "deck": deck_codes}

    counted = [row for row in rows if row["board"] in _COUNTED_BOARDS]
    total = sum(row["desired_quantity"] for row in counted)
    has_duplicate = any(
        row["desired_quantity"] > 1 and not _is_basic_land(row["name"], row["type_line"])
        for row in counted
    )
    if not has_commander:
        deck_codes.append("no_commander")
    if total != 100:
        deck_codes.append("wrong_size")
    if has_duplicate:
        deck_codes.append("singleton_violation")
    return {"cards": card_codes, "deck": deck_codes}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_deck_validation.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/services/deck_builder.py tests/test_deck_validation.py
git add backend/app/services/deck_builder.py backend/tests/test_deck_validation.py
git commit -m "$(cat <<'EOF'
Add deck legality validation (deck_violations) for ALI-12

Pure colour-identity + format-legality + singleton/size checks.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: deck_builder DB orchestration

**Files:**
- Modify: `backend/app/services/deck_builder.py`
- Test: `backend/tests/test_deck_builder_service.py`

**Interfaces:**
- Consumes: `inventory.move_holding`, `inventory.set_deck_entry`, `inventory.ensure_default_location`; `Deck`, `DeckEntry`, `Holding`, `Location`, `Card`.
- Produces:
  - `async add_card_to_deck(session, *, deck, card_id, board, quantity, foil=False, condition=CardCondition.NEAR_MINT, auto_allocate=True) -> None`
  - `async remove_card_from_deck(session, *, deck, card_id, board, quantity) -> None`
  - `async set_commander(session, *, deck, commander_card_id) -> None`
  - `async delete_deck(session, *, deck) -> None`
  - `async build_deck_view(session, *, deck) -> dict` returning `{"deck": Deck, "commander": Card | None, "cards": list[dict], "deck_violations": list[str]}` (see Step 3).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_deck_builder_service.py
"""deck_builder DB orchestration against a real, migrated Postgres (opt-in)."""

import os
import uuid

import pytest
from sqlalchemy import select

from app.core.db import async_session_factory
from app.models.card import Card
from app.models.enums import CardCondition, DeckBoard, DeckFormat
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_deck_builder_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'add_card_to_deck'`.
(If no DB is migrated locally, first run: `docker compose up -d db && cd backend && uv run alembic upgrade head`, and `export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/cabbycards`.)

- [ ] **Step 3: Implement the orchestration**

Append to `backend/app/services/deck_builder.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.deck import Deck, DeckEntry
from app.models.enums import CardCondition, DeckBoard, LocationKind
from app.models.holding import Holding
from app.models.location import Location
from app.services.inventory import (
    ensure_default_location,
    move_holding,
    set_deck_entry,
)


def _oracle_key(card: Card) -> str:
    # Group printings by oracle id for ownership maths; cards without one key on
    # their own id so they only ever match themselves.
    return str(card.oracle_id) if card.oracle_id is not None else f"cid:{card.id}"


async def _deck_user(session: AsyncSession, deck: Deck) -> "User":
    location = await session.get(Location, deck.location_id)
    return await session.get(User, location.user_id)


async def add_card_to_deck(
    session: AsyncSession,
    *,
    deck: Deck,
    card_id: int,
    board: DeckBoard,
    quantity: int,
    foil: bool = False,
    condition: CardCondition = CardCondition.NEAR_MINT,
    auto_allocate: bool = True,
) -> None:
    """Add ``quantity`` of a card to a deck: bump the intended entry, then pull
    up to ``quantity`` owned copies of the exact (card, foil, condition) stack
    from storage into the deck location.

    See: tests/test_deck_builder_service.py
    """
    entry = await session.scalar(
        select(DeckEntry).where(
            DeckEntry.deck_id == deck.location_id,
            DeckEntry.card_id == card_id,
            DeckEntry.board == board,
        )
    )
    current = entry.desired_quantity if entry is not None else 0
    await set_deck_entry(
        session, deck=deck, card_id=card_id, board=board, desired_quantity=current + quantity
    )
    if not auto_allocate:
        return

    # Pull matching copies from *any* of the user's storage locations (not just
    # Unsorted) — a card you own in "Binder A" should still build into the deck.
    user = await _deck_user(session, deck)
    candidates = (
        await session.scalars(
            select(Holding)
            .join(Location, Holding.location_id == Location.id)
            .where(
                Location.user_id == user.id,
                Location.kind == LocationKind.STORAGE,
                Holding.card_id == card_id,
                Holding.foil == foil,
                Holding.condition == condition,
            )
            .order_by(Holding.created_at)
        )
    ).all()
    remaining = quantity
    for holding in candidates:
        if remaining <= 0:
            break
        pull = min(remaining, holding.quantity)
        source = await session.get(Location, holding.location_id)
        await move_holding(
            session,
            from_location=source,
            to_location=deck.location,
            card_id=card_id,
            quantity=pull,
            foil=foil,
            condition=condition,
        )
        remaining -= pull


async def remove_card_from_deck(
    session: AsyncSession, *, deck: Deck, card_id: int, board: DeckBoard, quantity: int
) -> None:
    """Reduce a deck entry by ``quantity`` (deleting at zero) and move any
    deck-located copies of the card back to the user's Unsorted storage.

    See: tests/test_deck_builder_service.py
    """
    entry = await session.scalar(
        select(DeckEntry).where(
            DeckEntry.deck_id == deck.location_id,
            DeckEntry.card_id == card_id,
            DeckEntry.board == board,
        )
    )
    if entry is not None:
        entry.desired_quantity -= quantity
        if entry.desired_quantity <= 0:
            await session.delete(entry)

    storage = await ensure_default_location(session, await _deck_user(session, deck))
    deck_holdings = await session.scalars(
        select(Holding).where(
            Holding.location_id == deck.location_id, Holding.card_id == card_id
        )
    )
    for holding in deck_holdings.all():
        moved = min(quantity, holding.quantity)
        await move_holding(
            session,
            from_location=deck.location,
            to_location=storage,
            card_id=card_id,
            quantity=moved,
            foil=holding.foil,
            condition=holding.condition,
        )
        quantity -= moved
        if quantity <= 0:
            break
    await session.commit()


async def set_commander(session: AsyncSession, *, deck: Deck, commander_card_id: int | None) -> None:
    """Set (or clear) the deck's commander. Legality is reported by the view, not enforced here.

    See: tests/test_deck_builder_service.py
    """
    deck.commander_card_id = commander_card_id
    await session.commit()


async def delete_deck(session: AsyncSession, *, deck: Deck) -> None:
    """Relocate every deck-located holding to Unsorted, then delete the deck + its location.

    See: tests/test_deck_builder_service.py
    """
    storage = await ensure_default_location(session, await _deck_user(session, deck))
    holdings = await session.scalars(
        select(Holding).where(Holding.location_id == deck.location_id)
    )
    for holding in holdings.all():
        await move_holding(
            session,
            from_location=deck.location,
            to_location=storage,
            card_id=holding.card_id,
            quantity=holding.quantity,
            foil=holding.foil,
            condition=holding.condition,
        )
    location = await session.get(Location, deck.location_id)
    await session.delete(location)  # cascades to deck + deck_entries
    await session.commit()


async def build_deck_view(session: AsyncSession, *, deck: Deck) -> dict:
    """Compute the deck read model: per-card desired/allocated/owned/missing + violations.

    Allocation maths are oracle-level (any owned printing fulfils a desired card);
    the physical allocation that put copies here was printing-exact.

    See: tests/test_deck_builder_service.py
    """
    user = await _deck_user(session, deck)
    commander = (
        await session.get(Card, deck.commander_card_id)
        if deck.commander_card_id is not None
        else None
    )
    commander_identity = set(commander.data.get("color_identity", [])) if commander else set()

    entries = (
        await session.scalars(
            select(DeckEntry).where(DeckEntry.deck_id == deck.location_id)
        )
    ).all()

    user_holdings = (
        await session.scalars(
            select(Holding)
            .join(Location, Holding.location_id == Location.id)
            .where(Location.user_id == user.id)
        )
    ).all()

    allocated_by_key: dict[str, int] = {}
    owned_elsewhere_by_key: dict[str, int] = {}
    for holding in user_holdings:
        key = _oracle_key(holding.card)
        if holding.location_id == deck.location_id:
            allocated_by_key[key] = allocated_by_key.get(key, 0) + holding.quantity
        else:
            owned_elsewhere_by_key[key] = owned_elsewhere_by_key.get(key, 0) + holding.quantity

    rows: list[dict] = []
    for entry in entries:
        card = await session.get(Card, entry.card_id)
        key = _oracle_key(card)
        allocated = allocated_by_key.get(key, 0)
        owned_elsewhere = owned_elsewhere_by_key.get(key, 0)
        missing = max(0, entry.desired_quantity - allocated - owned_elsewhere)
        rows.append(
            {
                "card": card,
                "board": entry.board,
                "desired_quantity": entry.desired_quantity,
                "allocated_quantity": allocated,
                "owned_elsewhere_quantity": owned_elsewhere,
                "missing_quantity": missing,
            }
        )

    validation = deck_violations(
        [
            {
                "name": row["card"].name,
                "color_identity": row["card"].data.get("color_identity", []),
                "type_line": row["card"].data.get("type_line", ""),
                "legalities": row["card"].data.get("legalities", {}),
                "desired_quantity": row["desired_quantity"],
                "board": row["board"].value,
            }
            for row in rows
        ],
        format=deck.format,
        commander_identity=commander_identity,
        has_commander=commander is not None,
    )
    for row in rows:
        row["violations"] = validation["cards"].get(row["card"].name, [])

    return {"deck": deck, "commander": commander, "cards": rows, "deck_violations": validation["deck"]}
```

Add the missing import at the top of the file (with the other model imports):

```python
from app.models.user import User
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_deck_builder_service.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff check app/services/deck_builder.py tests/test_deck_builder_service.py
git add backend/app/services/deck_builder.py backend/tests/test_deck_builder_service.py
git commit -m "$(cat <<'EOF'
Add deck_builder orchestration: add/remove/delete + deck view (ALI-12)

Auto-allocates owned copies on add (printing-exact), de-allocates on remove,
relocates on delete; build_deck_view computes oracle-level ownership maths.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## COMMIT 2 — decks API

### Task 3: deck schemas, ownership dep, router

**Files:**
- Create: `backend/app/schemas/deck.py`
- Modify: `backend/app/api/deps.py` (add `get_owned_deck`)
- Create: `backend/app/api/routes/decks.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_decks_api.py`

**Interfaces:**
- Consumes: `deck_builder.*`, `inventory.create_deck`, `ScryfallService.get_card`, `get_current_user`, `get_session`, `get_scryfall_service`.
- Produces routes under `prefix="/decks"`: `POST /decks`, `GET /decks`, `GET /decks/{deck_id}`, `PATCH /decks/{deck_id}`, `DELETE /decks/{deck_id}`, `POST /decks/{deck_id}/cards`, `PATCH /decks/{deck_id}/cards`, `DELETE /decks/{deck_id}/cards/{card_id}`.
- Produces dep: `async get_owned_deck(session, user, deck_id) -> Deck | None`.

- [ ] **Step 1: Write the schemas**

```python
# backend/app/schemas/deck.py
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CardCondition, DeckBoard, DeckFormat
from app.schemas.card import CardOut


class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    format: DeckFormat = DeckFormat.COMMANDER
    commander_scryfall_id: uuid.UUID | None = None


class DeckUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    format: DeckFormat | None = None
    commander_scryfall_id: uuid.UUID | None = None


class DeckSummary(BaseModel):
    id: uuid.UUID
    name: str
    format: DeckFormat
    commander: CardOut | None
    distinct_cards: int
    owned_percent: int


class DeckCardOut(BaseModel):
    card: CardOut
    board: DeckBoard
    desired_quantity: int
    allocated_quantity: int
    owned_elsewhere_quantity: int
    missing_quantity: int
    violations: list[str]


class DeckView(BaseModel):
    id: uuid.UUID
    name: str
    format: DeckFormat
    commander: CardOut | None
    cards: list[DeckCardOut]
    deck_violations: list[str]


class AddDeckCardRequest(BaseModel):
    scryfall_id: uuid.UUID
    board: DeckBoard = DeckBoard.MAIN
    quantity: int = Field(default=1, ge=1)
    foil: bool = False
    condition: CardCondition = CardCondition.NEAR_MINT
    auto_allocate: bool = True


class UpdateDeckCardRequest(BaseModel):
    card_id: int
    board: DeckBoard
    desired_quantity: int = Field(ge=0)
```

- [ ] **Step 2: Add the ownership dependency**

In `backend/app/api/deps.py`, add (imports `select`, `Deck`, `Location` at top):

```python
from sqlalchemy import select

from app.models.deck import Deck
from app.models.location import Location


async def get_owned_deck(session: AsyncSession, user: User, deck_id: uuid.UUID) -> Deck | None:
    """Fetch a deck only if its location belongs to the user (else None).

    See: tests/test_decks_api.py
    """
    return await session.scalar(
        select(Deck)
        .join(Location, Deck.location_id == Location.id)
        .where(Deck.location_id == deck_id, Location.user_id == user.id)
    )
```

- [ ] **Step 3: Write the failing API tests**

```python
# backend/tests/test_decks_api.py
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_decks_api.py -v`
Expected: FAIL (404s / missing router — `/decks` not registered).

- [ ] **Step 5: Implement the router**

```python
# backend/app/api/routes/decks.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_deck, get_scryfall_service
from app.core.db import get_session
from app.models.deck import DeckEntry
from app.models.user import User
from app.schemas.deck import (
    AddDeckCardRequest,
    DeckCreate,
    DeckSummary,
    DeckUpdate,
    DeckView,
    UpdateDeckCardRequest,
)
from app.services.deck_builder import (
    add_card_to_deck,
    build_deck_view,
    delete_deck,
    remove_card_from_deck,
    set_commander,
)
from app.services.inventory import create_deck, list_locations
from app.services.scryfall import ScryfallError, ScryfallService

router = APIRouter(prefix="/decks", tags=["decks"])


def _view_to_schema(view: dict) -> DeckView:
    deck = view["deck"]
    return DeckView(
        id=deck.location_id,
        name=deck.location.name,
        format=deck.format,
        commander=view["commander"],
        cards=view["cards"],
        deck_violations=view["deck_violations"],
    )


async def _require_deck(session: AsyncSession, user: User, deck_id: uuid.UUID):
    deck = await get_owned_deck(session, user, deck_id)
    if deck is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return deck


async def _resolve_commander(
    scryfall: ScryfallService, scryfall_id: uuid.UUID | None
) -> int | None:
    if scryfall_id is None:
        return None
    try:
        card = await scryfall.get_card(scryfall_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Commander card not found") from exc
    return card.id


@router.post("", response_model=DeckView, status_code=status.HTTP_201_CREATED)
async def create_deck_endpoint(
    body: DeckCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scryfall: ScryfallService = Depends(get_scryfall_service),
) -> DeckView:
    commander_id = await _resolve_commander(scryfall, body.commander_scryfall_id)
    deck = await create_deck(
        session, user=user, name=body.name, format=body.format, commander_card_id=commander_id
    )
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.get("", response_model=list[DeckSummary])
async def list_decks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DeckSummary]:
    summaries: list[DeckSummary] = []
    for location in await list_locations(session, user):
        if location.kind.value != "deck":
            continue
        deck = await _require_deck(session, user, location.id)
        view = await build_deck_view(session, deck=deck)
        desired = sum(row["desired_quantity"] for row in view["cards"])
        owned = sum(
            min(row["desired_quantity"], row["allocated_quantity"] + row["owned_elsewhere_quantity"])
            for row in view["cards"]
        )
        summaries.append(
            DeckSummary(
                id=deck.location_id,
                name=deck.location.name,
                format=deck.format,
                commander=view["commander"],
                distinct_cards=len(view["cards"]),
                owned_percent=round(100 * owned / desired) if desired else 0,
            )
        )
    return summaries


@router.get("/{deck_id}", response_model=DeckView)
async def get_deck(
    deck_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeckView:
    deck = await _require_deck(session, user, deck_id)
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.patch("/{deck_id}", response_model=DeckView)
async def update_deck(
    deck_id: uuid.UUID,
    body: DeckUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scryfall: ScryfallService = Depends(get_scryfall_service),
) -> DeckView:
    deck = await _require_deck(session, user, deck_id)
    if body.name is not None:
        deck.location.name = body.name
    if body.format is not None:
        deck.format = body.format
    if body.commander_scryfall_id is not None:
        await set_commander(
            session, deck=deck, commander_card_id=await _resolve_commander(scryfall, body.commander_scryfall_id)
        )
    await session.commit()
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck_endpoint(
    deck_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    deck = await _require_deck(session, user, deck_id)
    await delete_deck(session, deck=deck)


@router.post("/{deck_id}/cards", response_model=DeckView, status_code=status.HTTP_201_CREATED)
async def add_deck_card(
    deck_id: uuid.UUID,
    body: AddDeckCardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scryfall: ScryfallService = Depends(get_scryfall_service),
) -> DeckView:
    deck = await _require_deck(session, user, deck_id)
    try:
        card = await scryfall.get_card(body.scryfall_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Card not found") from exc
    await add_card_to_deck(
        session,
        deck=deck,
        card_id=card.id,
        board=body.board,
        quantity=body.quantity,
        foil=body.foil,
        condition=body.condition,
        auto_allocate=body.auto_allocate,
    )
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.patch("/{deck_id}/cards", response_model=DeckView)
async def update_deck_card(
    deck_id: uuid.UUID,
    body: UpdateDeckCardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeckView:
    deck = await _require_deck(session, user, deck_id)
    entry = await session.scalar(
        select(DeckEntry).where(
            DeckEntry.deck_id == deck.location_id,
            DeckEntry.card_id == body.card_id,
            DeckEntry.board == body.board,
        )
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deck card not found")
    if body.desired_quantity == 0:
        await session.delete(entry)
    else:
        entry.desired_quantity = body.desired_quantity
    await session.commit()
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.delete("/{deck_id}/cards/{card_id}", response_model=DeckView)
async def remove_deck_card(
    deck_id: uuid.UUID,
    card_id: int,
    board: DeckBoard,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeckView:
    deck = await _require_deck(session, user, deck_id)
    await remove_card_from_deck(
        session, deck=deck, card_id=card_id, board=board, quantity=10_000
    )
    return _view_to_schema(await build_deck_view(session, deck=deck))
```

Add the missing `DeckBoard` import at the top of the router file:

```python
from app.models.enums import DeckBoard
```

- [ ] **Step 6: Register the router**

In `backend/app/main.py`:

```python
from app.api.routes import auth, cards, collection, decks
...
app.include_router(decks.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_decks_api.py -v`
Expected: PASS (5 tests).

- [ ] **Step 8: Lint and commit**

```bash
cd backend && uv run ruff check app/schemas/deck.py app/api/routes/decks.py app/api/deps.py tests/test_decks_api.py
git add backend/app/schemas/deck.py backend/app/api/routes/decks.py backend/app/api/deps.py backend/app/main.py backend/tests/test_decks_api.py
git commit -m "$(cat <<'EOF'
Add decks API: CRUD, contents, computed deck view (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## COMMIT 3 — Scryfall filtering + printings

### Task 4: `build_scryfall_query` + `search_cards`

**Files:**
- Modify: `backend/app/services/scryfall.py`
- Test: `backend/tests/test_scryfall_query.py`, extend `backend/tests/test_scryfall_service.py`

**Interfaces:**
- Produces: `build_scryfall_query(terms, *, identity=None, format=None) -> str` (pure); `async ScryfallService.search_cards(query, *, identity=None, format=None) -> list[Card]`; `async ScryfallService.list_printings(oracle_id) -> list[Card]`.

- [ ] **Step 1: Write the failing pure-helper tests**

```python
# backend/tests/test_scryfall_query.py
"""Pure Scryfall query-builder checks — no network, always run."""

from app.models.enums import DeckFormat
from app.services.scryfall import build_scryfall_query


def test_plain_query_when_no_filters() -> None:
    assert build_scryfall_query("sol ring") == "sol ring"


def test_identity_subset_filter() -> None:
    q = build_scryfall_query("counterspell", identity={"U", "W"}, format=DeckFormat.COMMANDER)
    assert "id<=uw" in q
    assert "legal:commander" in q
    assert q.startswith("counterspell")


def test_empty_identity_means_colourless_only() -> None:
    q = build_scryfall_query("sol ring", identity=set(), format=DeckFormat.COMMANDER)
    assert "id:c" in q


def test_format_only_when_no_identity() -> None:
    q = build_scryfall_query("llanowar", format=DeckFormat.STANDARD)
    assert "legal:standard" in q
    assert "id<=" not in q
    assert "id:c" not in q
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_scryfall_query.py -v`
Expected: FAIL with `cannot import name 'build_scryfall_query'`.

- [ ] **Step 3: Implement the helper + methods**

In `backend/app/services/scryfall.py`, add the pure helper near the top (after `is_card_stale`), importing `DeckFormat`:

```python
from app.models.enums import DeckFormat


def build_scryfall_query(
    terms: str, *, identity: set[str] | None = None, format: DeckFormat | None = None
) -> str:
    """Append colour-identity + format-legality filters to a Scryfall query.

    ``identity`` is a set of single-letter colours (the commander's identity); an
    empty set means a colourless commander, so only colourless cards are legal
    (``id:c``). A non-empty set uses Scryfall's subset operator (``id<=wu``).
    ``None`` adds no identity filter.

    See: tests/test_scryfall_query.py
    """
    parts = [terms.strip()]
    if identity is not None:
        if identity:
            parts.append(f"id<={''.join(sorted(c.lower() for c in identity))}")
        else:
            parts.append("id:c")
    if format is not None:
        parts.append(f"legal:{format.value}")
    return " ".join(part for part in parts if part)
```

Add methods to `ScryfallService` (reusing the existing `search` + `_ingest`):

```python
    async def search_cards(
        self, query: str, *, identity: set[str] | None = None, format: "DeckFormat | None" = None
    ) -> list[Card]:
        """Search Scryfall with colour-identity + format filters applied.

        See: tests/test_scryfall_service.py
        """
        return await self.search(build_scryfall_query(query, identity=identity, format=format))

    async def list_printings(self, oracle_id: uuid.UUID) -> list[Card]:
        """Every printing of a card (one row per set), newest first, all cached.

        See: tests/test_scryfall_service.py
        """
        payload = await self._fetch(
            "/cards/search",
            params={"q": f"oracleid:{oracle_id}", "unique": "prints", "order": "released"},
        )
        return [await self._ingest(data) for data in payload.get("data", [])]
```

- [ ] **Step 4: Add a MockTransport test for `list_printings`**

Append to `backend/tests/test_scryfall_service.py` (follow the file's existing MockTransport pattern — inspect it first for the helper that builds a service around a transport):

```python
async def test_list_printings_returns_and_caches_each(async_session) -> None:
    oracle = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cards/search"
        return httpx.Response(
            200,
            json={"data": [
                {"id": str(uuid.uuid4()), "oracle_id": str(oracle),
                 "name": "Sol Ring", "set": "c21"},
                {"id": str(uuid.uuid4()), "oracle_id": str(oracle),
                 "name": "Sol Ring", "set": "ltr"},
            ]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.test")
    async with ScryfallService(async_session, client=client) as service:
        printings = await service.list_printings(oracle)

    assert {p.data["set"] for p in printings} == {"c21", "ltr"}
```

> If `test_scryfall_service.py` has no `async_session` fixture, reuse whatever session fixture/helper that file already uses for `_ingest`-backed tests; do not invent a new one.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_scryfall_query.py -v && uv run pytest tests/test_scryfall_service.py -v`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check app/services/scryfall.py tests/test_scryfall_query.py
git add backend/app/services/scryfall.py backend/tests/test_scryfall_query.py backend/tests/test_scryfall_service.py
git commit -m "$(cat <<'EOF'
Add Scryfall colour-identity/legality search + printings (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: filtered card-search + printings endpoints

**Files:**
- Modify: `backend/app/api/routes/decks.py` (add `GET /decks/{deck_id}/card-search`)
- Modify: `backend/app/api/routes/cards.py` (add `GET /cards/{scryfall_id}/printings`)
- Test: extend `backend/tests/test_decks_api.py`

> Design note / deviation from spec: the filtered search lives at `GET /decks/{deck_id}/card-search` rather than `/cards/search?deck_id=…`, so the existing unauthenticated `/cards/search` stays untouched and deck context drives the filter server-side. The printings endpoint stays under `/cards`.

**Interfaces:**
- Consumes: `ScryfallService.search_cards`, `ScryfallService.list_printings`, `ScryfallService.get_card`, `get_owned_deck`.
- Produces: `GET /decks/{deck_id}/card-search?q=…&show_all=false -> list[CardOut]`; `GET /cards/{scryfall_id}/printings -> list[CardOut]`.

- [ ] **Step 1: Write the failing tests**

```python
# add to backend/tests/test_decks_api.py

class _FakeSearchScryfall:
    def __init__(self, results: list[Card]) -> None:
        self._results = results
        self.last_identity = "unset"

    async def search_cards(self, query, *, identity=None, format=None):
        self.last_identity = identity
        return self._results


async def test_card_search_uses_commander_identity() -> None:
    user, card = await _seed_user_and_card()
    fake = _FakeSearchScryfall([card])
    app.dependency_overrides[get_scryfall_service] = lambda: fake
    headers = _auth(user)
    async with _client() as ac:
        deck_id = (await ac.post("/decks", headers=headers, json={"name": "EDH"})).json()["id"]
        resp = await ac.get(f"/decks/{deck_id}/card-search?q=ring", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Sol Ring"
    assert fake.last_identity == set()  # no commander → colourless-only filter


async def test_card_search_show_all_drops_identity_filter() -> None:
    user, card = await _seed_user_and_card()
    fake = _FakeSearchScryfall([card])
    app.dependency_overrides[get_scryfall_service] = lambda: fake
    headers = _auth(user)
    async with _client() as ac:
        deck_id = (await ac.post("/decks", headers=headers, json={"name": "EDH"})).json()["id"]
        await ac.get(f"/decks/{deck_id}/card-search?q=ring&show_all=true", headers=headers)
    assert fake.last_identity is None  # show_all → no identity filter
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_decks_api.py -k card_search -v`
Expected: FAIL (404 — route not defined).

- [ ] **Step 3: Implement the deck card-search route**

Add to `backend/app/api/routes/decks.py` (imports `Query`, `CardOut`, `Card`):

```python
from fastapi import Query

from app.models.card import Card
from app.schemas.card import CardOut


@router.get("/{deck_id}/card-search", response_model=list[CardOut])
async def deck_card_search(
    deck_id: uuid.UUID,
    q: str = Query(min_length=1),
    show_all: bool = False,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scryfall: ScryfallService = Depends(get_scryfall_service),
) -> list[CardOut]:
    """Scryfall search filtered to the deck's commander identity + format.

    ``show_all`` drops the identity filter (the 'show all' escape hatch); the
    format-legality filter always applies.
    """
    deck = await _require_deck(session, user, deck_id)
    identity: set[str] | None = None
    if not show_all:
        if deck.commander_card_id is None:
            identity = set()
        else:
            commander = await session.get(Card, deck.commander_card_id)
            identity = set(commander.data.get("color_identity", []))
    try:
        return await scryfall.search_cards(q, identity=identity, format=deck.format)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
```

- [ ] **Step 4: Implement the printings route**

Add to `backend/app/api/routes/cards.py` BEFORE the `/{scryfall_id}` route (so the static `printings` suffix isn't swallowed):

```python
@router.get("/{scryfall_id}/printings", response_model=list[CardOut])
async def card_printings(
    scryfall_id: uuid.UUID,
    service: ScryfallService = Depends(get_scryfall_service),
) -> list[CardOut]:
    """All printings of a card (for the printing/finish selector)."""
    try:
        card = await service.get_card(scryfall_id)
        if card.oracle_id is None:
            return [card]
        return await service.list_printings(card.oracle_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_decks_api.py -v`
Expected: PASS (all deck API tests including the two new search tests).

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff check app/api/routes/decks.py app/api/routes/cards.py tests/test_decks_api.py
git add backend/app/api/routes/decks.py backend/app/api/routes/cards.py backend/tests/test_decks_api.py
git commit -m "$(cat <<'EOF'
Add deck-filtered card search + printings endpoints (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## COMMIT 4 — frontend store + routing

### Task 6: `stores/decks.ts`

**Files:**
- Create: `frontend/src/stores/decks.ts`
- Test: `frontend/src/stores/decks.spec.ts`

**Interfaces:**
- Produces a Pinia store `useDecksStore` with `decks`, `current` refs and actions `fetchDecks`, `createDeck(name, format?, commanderScryfallId?)`, `fetchDeck(id)`, `addCard(deckId, payload)`, `updateCard(deckId, payload)`, `removeCard(deckId, cardId, board)`, `setCommander(deckId, scryfallId)`, `deleteDeck(deckId)`.

- [ ] **Step 1: Write the failing store test**

```ts
// frontend/src/stores/decks.spec.ts
import { createPinia, setActivePinia } from "pinia"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { useDecksStore } from "@/stores/decks"

describe("decks store", () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it("fetches the deck list", async () => {
    const spy = vi.spyOn(api, "apiFetch").mockResolvedValue([
      { id: "d1", name: "EDH", format: "commander", commander: null, distinct_cards: 0, owned_percent: 0 },
    ])
    const store = useDecksStore()
    await store.fetchDecks()
    expect(spy).toHaveBeenCalledWith("/decks")
    expect(store.decks).toHaveLength(1)
  })

  it("adds a card and stores the returned view", async () => {
    const view = { id: "d1", name: "EDH", format: "commander", commander: null, cards: [], deck_violations: [] }
    const spy = vi.spyOn(api, "apiFetch").mockResolvedValue(view)
    const store = useDecksStore()
    await store.addCard("d1", { scryfall_id: "s1", board: "main", quantity: 1, foil: false, condition: "nm" })
    expect(spy).toHaveBeenCalledWith("/decks/d1/cards", expect.objectContaining({ method: "POST" }))
    expect(store.current?.id).toBe("d1")
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm run test -- decks.spec`
Expected: FAIL — cannot resolve `@/stores/decks`.

- [ ] **Step 3: Implement the store**

```ts
// frontend/src/stores/decks.ts
import { defineStore } from "pinia"
import { ref } from "vue"

import { apiFetch } from "@/lib/api"
import type { HoldingCard } from "@/stores/collection"

export interface DeckSummary {
  id: string
  name: string
  format: string
  commander: HoldingCard | null
  distinct_cards: number
  owned_percent: number
}

export interface DeckCard {
  card: HoldingCard
  board: string
  desired_quantity: number
  allocated_quantity: number
  owned_elsewhere_quantity: number
  missing_quantity: number
  violations: string[]
}

export interface DeckView {
  id: string
  name: string
  format: string
  commander: HoldingCard | null
  cards: DeckCard[]
  deck_violations: string[]
}

export interface AddDeckCardPayload {
  scryfall_id: string
  board: string
  quantity: number
  foil: boolean
  condition: string
}

export const useDecksStore = defineStore("decks", () => {
  const decks = ref<DeckSummary[]>([])
  const current = ref<DeckView | null>(null)

  async function fetchDecks(): Promise<void> {
    decks.value = await apiFetch<DeckSummary[]>("/decks")
  }

  async function createDeck(
    name: string,
    format = "commander",
    commanderScryfallId: string | null = null,
  ): Promise<DeckView> {
    const view = await apiFetch<DeckView>("/decks", {
      method: "POST",
      body: JSON.stringify({ name, format, commander_scryfall_id: commanderScryfallId }),
    })
    current.value = view
    return view
  }

  async function fetchDeck(id: string): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${id}`)
  }

  async function addCard(deckId: string, payload: AddDeckCardPayload): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}/cards`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async function updateCard(
    deckId: string,
    payload: { card_id: number; board: string; desired_quantity: number },
  ): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}/cards`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
  }

  async function removeCard(deckId: string, cardId: number, board: string): Promise<void> {
    current.value = await apiFetch<DeckView>(
      `/decks/${deckId}/cards/${cardId}?board=${board}`,
      { method: "DELETE" },
    )
  }

  async function setCommander(deckId: string, scryfallId: string): Promise<void> {
    current.value = await apiFetch<DeckView>(`/decks/${deckId}`, {
      method: "PATCH",
      body: JSON.stringify({ commander_scryfall_id: scryfallId }),
    })
  }

  async function deleteDeck(deckId: string): Promise<void> {
    await apiFetch(`/decks/${deckId}`, { method: "DELETE" })
    decks.value = decks.value.filter((deck) => deck.id !== deckId)
  }

  return {
    decks, current,
    fetchDecks, createDeck, fetchDeck, addCard, updateCard, removeCard, setCommander, deleteDeck,
  }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm run test -- decks.spec`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && npm run lint
git add frontend/src/stores/decks.ts frontend/src/stores/decks.spec.ts
git commit -m "$(cat <<'EOF'
Add decks Pinia store (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: routing + nav

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add the routes**

In `frontend/src/router/index.ts`, import the views and add two routes inside `routes`:

```ts
import DeckBuilderView from "@/views/DeckBuilderView.vue"
import DecksView from "@/views/DecksView.vue"
...
    { path: "/decks", name: "decks", component: DecksView, meta: { requiresAuth: true } },
    { path: "/decks/:id", name: "deck", component: DeckBuilderView, meta: { requiresAuth: true } },
```

- [ ] **Step 2: Add nav links**

In `frontend/src/App.vue`, add `<RouterLink to="/">Collection</RouterLink>` and `<RouterLink to="/decks">Decks</RouterLink>` to the existing header/nav, matching the file's current markup and Tailwind classes.

- [ ] **Step 3: Verify build (views created in Commit 5; use placeholders to keep the build green)**

Create minimal placeholder views so the router resolves now, fleshed out next commit:

```vue
<!-- frontend/src/views/DecksView.vue -->
<template><div>Decks</div></template>
```
```vue
<!-- frontend/src/views/DeckBuilderView.vue -->
<template><div>Deck builder</div></template>
```

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/App.vue frontend/src/views/DecksView.vue frontend/src/views/DeckBuilderView.vue
git commit -m "$(cat <<'EOF'
Add decks routes + nav with placeholder views (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## COMMIT 5 — views

### Task 8: `DecksView` (list + create)

**Files:**
- Modify: `frontend/src/views/DecksView.vue`

**Interfaces:**
- Consumes: `useDecksStore` (`decks`, `fetchDecks`, `createDeck`, `deleteDeck`), `RouterLink`, `CardView`.

- [ ] **Step 1: Implement the view**

Replace the placeholder `DecksView.vue` with a list-and-create view following `CollectionView.vue`'s structure (same store-on-mount pattern, Tailwind classes, brand colours):

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"

import { useDecksStore } from "@/stores/decks"

const store = useDecksStore()
const router = useRouter()
const newName = ref("")

onMounted(() => void store.fetchDecks())

async function create(): Promise<void> {
  const name = newName.value.trim()
  if (!name) return
  const view = await store.createDeck(name)
  newName.value = ""
  await router.push(`/decks/${view.id}`)
}
</script>

<template>
  <section class="mx-auto max-w-4xl p-4">
    <h1 class="mb-4 text-xl font-semibold">Decks</h1>
    <form class="mb-6 flex gap-2" @submit.prevent="create">
      <input
        v-model="newName"
        placeholder="New deck name…"
        class="flex-1 rounded border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
      />
      <button type="submit" class="rounded bg-brand-500 px-4 py-2 text-sm font-medium text-white">
        Create
      </button>
    </form>

    <ul class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <li
        v-for="deck in store.decks"
        :key="deck.id"
        class="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
      >
        <RouterLink :to="`/decks/${deck.id}`" class="font-medium hover:text-brand-500">
          {{ deck.name }}
        </RouterLink>
        <p class="mt-1 text-xs text-slate-500">
          {{ deck.format }} · {{ deck.distinct_cards }} cards · {{ deck.owned_percent }}% owned
        </p>
        <button
          type="button"
          class="mt-2 text-xs text-red-600 hover:underline"
          @click="store.deleteDeck(deck.id)"
        >
          Delete
        </button>
      </li>
    </ul>
    <p v-if="!store.decks.length" class="text-sm text-slate-500">No decks yet — create one above.</p>
  </section>
</template>
```

- [ ] **Step 2: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/DecksView.vue
git commit -m "$(cat <<'EOF'
Add DecksView: list + create decks (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `DeckBuilderView` (board tabs, type columns, validation)

**Files:**
- Modify: `frontend/src/views/DeckBuilderView.vue`

**Interfaces:**
- Consumes: `useDecksStore` (`current`, `fetchDeck`, `removeCard`), `useRoute`, `CardView`, `AddCardSearch`, `PrintingSelector` (added in Commit 6 — wire the add panel there). This task delivers the read-only layout (header, board tabs, type columns, validation panel); the add panel is wired in Task 11.

- [ ] **Step 1: Implement the layout**

Replace the placeholder with the builder. Group `current.cards` by board (tabs) and by primary type (columns) derived from `card.data.type_line`. No nested ternaries — use a helper:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { useDecksStore, type DeckCard } from "@/stores/decks"

const store = useDecksStore()
const route = useRoute()
const deckId = route.params.id as string
const activeBoard = ref("main")

onMounted(() => void store.fetchDeck(deckId))

const TYPE_ORDER = [
  "Creature", "Planeswalker", "Instant", "Sorcery",
  "Artifact", "Enchantment", "Land", "Other",
]

function primaryType(card: DeckCard): string {
  const line = String(card.card.data.type_line ?? "")
  const match = TYPE_ORDER.find((t) => t !== "Other" && line.includes(t))
  return match ?? "Other"
}

const boardCards = computed(() => store.current?.cards.filter((c) => c.board === activeBoard.value) ?? [])

const columns = computed(() => {
  const groups: Record<string, DeckCard[]> = {}
  for (const card of boardCards.value) {
    const type = primaryType(card)
    groups[type] = groups[type] ?? []
    groups[type].push(card)
  }
  return TYPE_ORDER.filter((t) => groups[t]?.length).map((t) => ({ type: t, cards: groups[t] }))
})

function ownershipClass(card: DeckCard): string {
  if (card.missing_quantity > 0) return "text-red-600"
  if (card.allocated_quantity < card.desired_quantity) return "text-amber-600"
  return "text-emerald-600"
}
</script>

<template>
  <section v-if="store.current" class="mx-auto max-w-6xl p-4">
    <header class="mb-4">
      <h1 class="text-xl font-semibold">{{ store.current.name }}</h1>
      <p class="text-xs text-slate-500">
        {{ store.current.format }}
        <span v-if="store.current.commander"> · {{ store.current.commander.name }}</span>
      </p>
      <ul v-if="store.current.deck_violations.length" class="mt-2 text-xs text-red-600">
        <li v-for="code in store.current.deck_violations" :key="code">⚠ {{ code }}</li>
      </ul>
    </header>

    <nav class="mb-4 flex gap-2 border-b border-slate-200 dark:border-slate-700">
      <button
        v-for="board in ['main', 'side', 'maybe', 'command']"
        :key="board"
        type="button"
        class="px-3 py-2 text-sm capitalize"
        :class="board === activeBoard ? 'border-b-2 border-brand-500 font-medium' : 'text-slate-500'"
        @click="activeBoard = board"
      >
        {{ board }}
      </button>
    </nav>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="column in columns" :key="column.type">
        <h2 class="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">
          {{ column.type }} ({{ column.cards.length }})
        </h2>
        <ul class="space-y-1">
          <li
            v-for="entry in column.cards"
            :key="entry.card.id"
            class="flex items-center justify-between rounded border border-slate-200 px-2 py-1 text-sm dark:border-slate-700"
          >
            <span>{{ entry.desired_quantity }}× {{ entry.card.name }}</span>
            <span class="flex items-center gap-2">
              <span :class="ownershipClass(entry)" class="text-xs">
                {{ entry.allocated_quantity }}/{{ entry.desired_quantity }}
              </span>
              <button
                type="button"
                class="text-xs text-red-600 hover:underline"
                @click="store.removeCard(deckId, entry.card.id, entry.board)"
              >
                ✕
              </button>
            </span>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/DeckBuilderView.vue
git commit -m "$(cat <<'EOF'
Add DeckBuilderView: board tabs, type columns, ownership + validation (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## COMMIT 6 — shared PrintingSelector + add integration

### Task 10: `PrintingSelector` component

**Files:**
- Create: `frontend/src/components/PrintingSelector.vue`
- Test: `frontend/src/components/PrintingSelector.spec.ts`

**Interfaces:**
- Props: `oracleScryfallId: string` (a printing's scryfall id, used to fetch all printings).
- Emits: `select: [{ scryfall_id: string; foil: boolean; condition: string }]`.
- Consumes: `apiFetch` (`GET /cards/{scryfall_id}/printings`).

- [ ] **Step 1: Write the failing spec**

```ts
// frontend/src/components/PrintingSelector.spec.ts
import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import PrintingSelector from "@/components/PrintingSelector.vue"

describe("PrintingSelector", () => {
  afterEach(() => vi.restoreAllMocks())

  it("loads printings and emits the chosen printing + finish + condition", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue([
      { scryfall_id: "s-c21", name: "Sol Ring", data: { set: "c21", finishes: ["nonfoil", "foil"] } },
      { scryfall_id: "s-ltr", name: "Sol Ring", data: { set: "ltr", finishes: ["nonfoil"] } },
    ])
    const wrapper = mount(PrintingSelector, { props: { oracleScryfallId: "s-c21" } })
    await flushPromises()

    await wrapper.find("button[data-test='confirm']").trigger("click")
    const events = wrapper.emitted("select")
    expect(events).toBeTruthy()
    expect(events?.[0][0]).toMatchObject({ scryfall_id: "s-c21", condition: "nm" })
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm run test -- PrintingSelector`
Expected: FAIL — cannot resolve component.

- [ ] **Step 3: Implement the component**

```vue
<!-- frontend/src/components/PrintingSelector.vue -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { apiFetch } from "@/lib/api"

interface Printing {
  scryfall_id: string
  name: string
  data: { set?: string; collector_number?: string; finishes?: string[] }
}

const props = defineProps<{ oracleScryfallId: string }>()
const emit = defineEmits<{ select: [{ scryfall_id: string; foil: boolean; condition: string }] }>()

const CONDITIONS = ["nm", "lp", "mp", "hp", "dmg"]

const printings = ref<Printing[]>([])
const selectedId = ref("")
const finish = ref("nonfoil")
const condition = ref("nm")

onMounted(async () => {
  printings.value = await apiFetch<Printing[]>(`/cards/${props.oracleScryfallId}/printings`)
  selectedId.value = printings.value[0]?.scryfall_id ?? props.oracleScryfallId
})

const selected = computed(() => printings.value.find((p) => p.scryfall_id === selectedId.value))
const finishes = computed(() => selected.value?.data.finishes ?? ["nonfoil"])

function confirm(): void {
  emit("select", {
    scryfall_id: selectedId.value,
    foil: finish.value === "foil" || finish.value === "etched",
    condition: condition.value,
  })
}
</script>

<template>
  <div class="space-y-2 rounded border border-slate-200 p-3 dark:border-slate-700">
    <label class="block text-xs">
      Printing
      <select v-model="selectedId" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="p in printings" :key="p.scryfall_id" :value="p.scryfall_id">
          {{ (p.data.set ?? "?").toUpperCase() }} · {{ p.data.collector_number ?? "" }}
        </option>
      </select>
    </label>
    <label class="block text-xs">
      Finish
      <select v-model="finish" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="f in finishes" :key="f" :value="f">{{ f }}</option>
      </select>
    </label>
    <label class="block text-xs">
      Condition
      <select v-model="condition" class="mt-1 w-full rounded border px-2 py-1 text-sm dark:bg-slate-800">
        <option v-for="c in CONDITIONS" :key="c" :value="c">{{ c.toUpperCase() }}</option>
      </select>
    </label>
    <button
      type="button"
      data-test="confirm"
      class="w-full rounded bg-brand-500 px-3 py-1.5 text-sm font-medium text-white"
      @click="confirm"
    >
      Add to deck
    </button>
  </div>
</template>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm run test -- PrintingSelector`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && npm run lint
git add frontend/src/components/PrintingSelector.vue frontend/src/components/PrintingSelector.spec.ts
git commit -m "$(cat <<'EOF'
Add shared PrintingSelector component (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: wire add-card into the deck builder

**Files:**
- Modify: `frontend/src/components/AddCardSearch.vue` (accept an optional search endpoint)
- Modify: `frontend/src/views/DeckBuilderView.vue` (add panel: search → PrintingSelector → store.addCard)

**Interfaces:**
- `AddCardSearch` gains an optional prop `searchPath?: string` (default `/cards/search`); it builds the request as `${searchPath}${searchPath.includes('?') ? '&' : '?'}q=…`.

- [ ] **Step 1: Parameterise AddCardSearch's endpoint**

In `frontend/src/components/AddCardSearch.vue`:

```ts
const props = withDefaults(defineProps<{ searchPath?: string }>(), { searchPath: "/cards/search" })
```

Change the fetch line in `runSearch` to:

```ts
    const sep = props.searchPath.includes("?") ? "&" : "?"
    results.value = await apiFetch<SearchCard[]>(
      `${props.searchPath}${sep}q=${encodeURIComponent(term)}`,
    )
```

(Existing collection usage passes no prop → unchanged behaviour. The existing `AddCardSearch.spec.ts` must still pass.)

- [ ] **Step 2: Run the existing component test to confirm no regression**

Run: `cd frontend && npm run test -- AddCardSearch`
Expected: PASS (unchanged).

- [ ] **Step 3: Add the deck builder's add panel**

In `frontend/src/views/DeckBuilderView.vue`, import `AddCardSearch` and `PrintingSelector`, hold the picked card, and wire it:

```ts
import AddCardSearch from "@/components/AddCardSearch.vue"
import PrintingSelector from "@/components/PrintingSelector.vue"

interface SearchCard { scryfall_id: string; name: string; data: Record<string, unknown> }
const picked = ref<SearchCard | null>(null)

function onPick(card: SearchCard): void {
  picked.value = card
}

async function onSelectPrinting(payload: { scryfall_id: string; foil: boolean; condition: string }): Promise<void> {
  await store.addCard(deckId, { ...payload, board: activeBoard.value, quantity: 1 })
  picked.value = null
}
```

Add to the template (e.g. an aside beside the columns):

```vue
    <aside class="mt-6">
      <h2 class="mb-2 text-sm font-medium">Add a card</h2>
      <AddCardSearch :search-path="`/decks/${deckId}/card-search`" @add="onPick" />
      <PrintingSelector
        v-if="picked"
        :oracle-scryfall-id="picked.scryfall_id"
        class="mt-3"
        @select="onSelectPrinting"
      />
    </aside>
```

- [ ] **Step 4: Verify build, lint, full frontend test run**

Run: `cd frontend && npm run build && npm run lint && npm run test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AddCardSearch.vue frontend/src/views/DeckBuilderView.vue
git commit -m "$(cat <<'EOF'
Wire deck-filtered add-card + PrintingSelector into the builder (ALI-12)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification (before opening the PR)

- [ ] Backend hermetic suite: `cd backend && uv run pytest` → all pass (DB tests skip without the flag).
- [ ] Backend DB suite: `cd backend && CABBYCARDS_DB_TESTS=1 uv run pytest` (with a migrated DB + `DATABASE_URL`) → all pass.
- [ ] Backend lint: `cd backend && uv run ruff check .` → clean.
- [ ] Frontend: `cd frontend && npm run test && npm run lint && npm run build` → all pass.
- [ ] Manual smoke (optional): `docker compose up --build`, register, create a deck, add an owned + an unowned card, confirm allocation + missing counts + validation panel.
- [ ] Open one PR off `madcabbage/ali-12-…`; do not push without asking the user first.

## Spec coverage map

- Deck CRUD + set commander → Tasks 3.
- deck_entries by board → Tasks 2, 3 (`add`/`update`/`remove` card).
- Colour-identity + format-legality filtering → Tasks 4 (query), 5 (endpoint), 1 (validation).
- Build from collection / auto-allocate (printing-exact) → Task 2.
- Computed deck view (oracle-level ownership) → Task 2 (`build_deck_view`), 3 (schema).
- Frontend deck-builder UI → Tasks 6–11.
- Shared PrintingSelector → Task 10, reused per ALI-22 later.
- Out of scope (ALI-10 pagination, ALI-13 owned-only toggle, ALI-14 export, ALI-22 retrofit) → unchanged.
