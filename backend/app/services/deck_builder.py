"""Deck building: legality validation (pure) + allocation orchestration (DB).

Sits on top of the ALI-18 inventory primitives — it never writes holdings or
entries directly, it calls move_holding / set_deck_entry.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.deck import Deck, DeckEntry
from app.models.enums import CardCondition, DeckBoard, DeckFormat, LocationKind
from app.models.holding import Holding
from app.models.location import Location
from app.models.user import User
from app.services.inventory import (
    ensure_default_location,
    move_holding,
    set_deck_entry,
)

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


def _oracle_key(card: Card) -> str:
    # Group printings by oracle id for ownership maths; cards without one key on
    # their own id so they only ever match themselves.
    return str(card.oracle_id) if card.oracle_id is not None else f"cid:{card.id}"


async def _deck_user(session: AsyncSession, deck: Deck) -> User:
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


async def set_commander(
    session: AsyncSession, *, deck: Deck, commander_card_id: int | None
) -> None:
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
    session.expire_all()  # clear identity map so subsequent get() re-queries


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

    return {
        "deck": deck,
        "commander": commander,
        "cards": rows,
        "deck_violations": validation["deck"],
    }
