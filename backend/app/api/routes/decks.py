import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_deck, get_scryfall_service
from app.core.db import get_session
from app.models.card import Card
from app.models.deck import Deck, DeckEntry
from app.models.enums import DeckBoard
from app.models.user import User
from app.schemas.card import CardOut
from app.schemas.deck import (
    AddDeckCardRequest,
    DeckCreate,
    DeckSummary,
    DeckUpdate,
    DeckView,
    UpdateDeckCardRequest,
)
from app.services.card_search import name_sort_key
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


async def _require_deck(session: AsyncSession, user: User, deck_id: uuid.UUID) -> Deck:
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
    """Create a new deck for the authenticated user.

    See: tests/test_decks_api.py
    """
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
    """List all decks owned by the authenticated user.

    See: tests/test_decks_api.py
    """
    summaries: list[DeckSummary] = []
    for location in await list_locations(session, user):
        if location.kind.value != "deck":
            continue
        deck = await get_owned_deck(session, user, location.id)
        if deck is None:
            continue
        view = await build_deck_view(session, deck=deck)
        desired = sum(row["desired_quantity"] for row in view["cards"])
        owned = sum(
            min(row["desired_quantity"],
                row["allocated_quantity"] + row["owned_elsewhere_quantity"])
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
    """Fetch the full deck view for a single deck.

    See: tests/test_decks_api.py
    """
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
    """Update deck metadata (name, format, commander).

    See: tests/test_decks_api.py
    """
    deck = await _require_deck(session, user, deck_id)
    if body.name is not None:
        deck.location.name = body.name
    if body.format is not None:
        deck.format = body.format
    if body.commander_scryfall_id is not None:
        commander_id = await _resolve_commander(scryfall, body.commander_scryfall_id)
        await set_commander(session, deck=deck, commander_card_id=commander_id)
    await session.commit()
    return _view_to_schema(await build_deck_view(session, deck=deck))


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck_endpoint(
    deck_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a deck, relocating all its holdings back to Unsorted storage.

    See: tests/test_decks_api.py
    """
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
    """Add a card to a deck's intended list (and auto-allocate from storage if owned).

    See: tests/test_decks_api.py
    """
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
    """Update the desired quantity for a card on a board (0 removes the entry).

    See: tests/test_decks_api.py
    """
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
    """Remove a card from a deck's intended list and return its copies to storage.

    See: tests/test_decks_api.py
    """
    deck = await _require_deck(session, user, deck_id)
    await remove_card_from_deck(
        session, deck=deck, card_id=card_id, board=board, quantity=10_000
    )
    return _view_to_schema(await build_deck_view(session, deck=deck))


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
    format-legality filter always applies. Results are re-ranked by name
    relevance to ``q`` — identically to the collection ``/cards/search`` route —
    since Scryfall returns full-text relevance order (surfacing "Solarion" ahead
    of "Sol Ring" for "sol ri").

    See: tests/test_decks_api.py
    """
    deck = await _require_deck(session, user, deck_id)
    identity: set[str] | None = None
    if not show_all:
        if deck.commander_card_id is None:
            identity = set()
        else:
            commander = await session.get(Card, deck.commander_card_id)
            identity = set()
            if commander is not None:
                identity = set(commander.data.get("color_identity", []))
    try:
        cards = await scryfall.search_cards(q, identity=identity, deck_format=deck.format)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return sorted(cards, key=lambda card: name_sort_key(q, card.name))
