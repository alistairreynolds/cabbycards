from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deck import Deck, DeckEntry
from app.models.enums import CardCondition, DeckBoard, DeckFormat, LocationKind
from app.models.holding import Holding
from app.models.location import Location
from app.models.user import User

_DEFAULT_STORAGE_NAME = "Unsorted"


class InsufficientQuantity(Exception):
    """A move asked for more copies than the source location holds."""


async def ensure_default_location(session: AsyncSession, user: User) -> Location:
    """Get-or-create the user's default storage location ("Unsorted").

    See: tests/test_inventory_service.py
    """
    location = await session.scalar(
        select(Location).where(
            Location.user_id == user.id,
            Location.kind == LocationKind.STORAGE,
            Location.name == _DEFAULT_STORAGE_NAME,
        )
    )
    if location is None:
        location = Location(user_id=user.id, name=_DEFAULT_STORAGE_NAME, kind=LocationKind.STORAGE)
        session.add(location)
        await session.commit()
    return location


async def create_storage_location(session: AsyncSession, user: User, name: str) -> Location:
    """Create a named storage location (binder/box).

    See: tests/test_inventory_service.py
    """
    location = Location(user_id=user.id, name=name, kind=LocationKind.STORAGE)
    session.add(location)
    await session.commit()
    return location


async def create_deck(
    session: AsyncSession,
    *,
    user: User,
    name: str,
    format: DeckFormat,
    commander_card_id: int | None = None,
) -> Deck:
    """Create a deck — a location of kind ``deck`` plus its deck attributes.

    See: tests/test_inventory_service.py
    """
    location = Location(user_id=user.id, name=name, kind=LocationKind.DECK)
    deck = Deck(location=location, format=format, commander_card_id=commander_card_id)
    session.add(deck)
    await session.commit()
    return deck


async def _find_holding(
    session: AsyncSession, *, location_id, card_id: int, foil: bool, condition: CardCondition
) -> Holding | None:
    return await session.scalar(
        select(Holding).where(
            Holding.location_id == location_id,
            Holding.card_id == card_id,
            Holding.foil == foil,
            Holding.condition == condition,
        )
    )


async def add_holding(
    session: AsyncSession,
    *,
    location: Location,
    card_id: int,
    quantity: int,
    foil: bool = False,
    condition: CardCondition = CardCondition.NEAR_MINT,
) -> Holding:
    """Add copies of a card to a location, merging into the matching stack.

    See: tests/test_inventory_service.py
    """
    holding = await _find_holding(
        session, location_id=location.id, card_id=card_id, foil=foil, condition=condition
    )
    if holding is None:
        holding = Holding(
            location_id=location.id,
            card_id=card_id,
            quantity=quantity,
            foil=foil,
            condition=condition,
        )
        session.add(holding)
    else:
        holding.quantity += quantity
    await session.commit()
    return holding


async def move_holding(
    session: AsyncSession,
    *,
    from_location: Location,
    to_location: Location,
    card_id: int,
    quantity: int,
    foil: bool = False,
    condition: CardCondition = CardCondition.NEAR_MINT,
) -> None:
    """Move copies of a card from one location to another (deck or storage).

    Raises InsufficientQuantity (leaving everything untouched) if the source
    doesn't hold enough. The source stack is removed when it hits zero.

    See: tests/test_inventory_service.py
    """
    source = await _find_holding(
        session, location_id=from_location.id, card_id=card_id, foil=foil, condition=condition
    )
    if source is None or source.quantity < quantity:
        raise InsufficientQuantity()

    source.quantity -= quantity
    if source.quantity == 0:
        await session.delete(source)

    destination = await _find_holding(
        session, location_id=to_location.id, card_id=card_id, foil=foil, condition=condition
    )
    if destination is None:
        destination = Holding(
            location_id=to_location.id,
            card_id=card_id,
            quantity=quantity,
            foil=foil,
            condition=condition,
        )
        session.add(destination)
    else:
        destination.quantity += quantity

    await session.commit()


async def set_deck_entry(
    session: AsyncSession,
    *,
    deck: Deck,
    card_id: int,
    board: DeckBoard,
    desired_quantity: int,
) -> DeckEntry:
    """Set a deck's desired quantity for a card on a board (upsert).

    See: tests/test_inventory_service.py
    """
    entry = await session.scalar(
        select(DeckEntry).where(
            DeckEntry.deck_id == deck.location_id,
            DeckEntry.card_id == card_id,
            DeckEntry.board == board,
        )
    )
    if entry is None:
        entry = DeckEntry(
            deck_id=deck.location_id,
            card_id=card_id,
            board=board,
            desired_quantity=desired_quantity,
        )
        session.add(entry)
    else:
        entry.desired_quantity = desired_quantity
    await session.commit()
    return entry
