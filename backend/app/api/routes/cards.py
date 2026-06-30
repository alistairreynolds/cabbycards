import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_scryfall_service
from app.core.db import get_session
from app.schemas.card import CardOut
from app.services.card_search import name_sort_key, search_cached_cards
from app.services.scryfall import ScryfallError, ScryfallService

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search", response_model=list[CardOut])
async def search_cards(
    q: str = Query(min_length=1, description="Scryfall search syntax"),
    service: ScryfallService = Depends(get_scryfall_service),
) -> list[CardOut]:
    """Search Scryfall live; every returned card is cached locally as a side effect.

    Results are re-ranked by name relevance to the query, since Scryfall returns
    them by full-text relevance (which ranks "Solemn Offering" for "sol ring").
    """
    try:
        cards = await service.search(q)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return sorted(cards, key=lambda card: name_sort_key(q, card.name))


@router.get("/local-search", response_model=list[CardOut])
async def local_search(
    q: str = Query(min_length=1, description="Fuzzy name match over cached cards"),
    session: AsyncSession = Depends(get_session),
) -> list[CardOut]:
    """Fuzzy-search only cards already cached locally (no Scryfall round-trip)."""
    return list(await search_cached_cards(session, q))


# The printings route must appear before /{scryfall_id} so the static suffix is
# not swallowed by the dynamic segment.
@router.get("/{scryfall_id}/printings", response_model=list[CardOut])
async def card_printings(
    scryfall_id: uuid.UUID,
    service: ScryfallService = Depends(get_scryfall_service),
) -> list[CardOut]:
    """All printings of a card (for the printing/finish selector).

    See: tests/test_cards_api.py
    """
    try:
        card = await service.get_card(scryfall_id)
        if card.oracle_id is None:
            return [card]
        return await service.list_printings(card.oracle_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# Declared after the static paths above so they are not swallowed by this route.
@router.get("/{scryfall_id}", response_model=CardOut)
async def get_card(
    scryfall_id: uuid.UUID,
    service: ScryfallService = Depends(get_scryfall_service),
) -> CardOut:
    """Fetch one card by Scryfall id, serving from cache when fresh."""
    try:
        card = await service.get_card(scryfall_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return card
