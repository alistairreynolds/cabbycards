import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_scryfall_service
from app.core.db import get_session
from app.schemas.card import CardOut
from app.services.card_search import search_cached_cards
from app.services.scryfall import ScryfallError, ScryfallService

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search", response_model=list[CardOut])
async def search_cards(
    q: str = Query(min_length=1, description="Scryfall search syntax"),
    service: ScryfallService = Depends(get_scryfall_service),
) -> list[CardOut]:
    """Search Scryfall live; every returned card is cached locally as a side effect."""
    try:
        cards = await service.search(q)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return cards


@router.get("/local-search", response_model=list[CardOut])
async def local_search(
    q: str = Query(min_length=1, description="Fuzzy name match over cached cards"),
    session: AsyncSession = Depends(get_session),
) -> list[CardOut]:
    """Fuzzy-search only cards already cached locally (no Scryfall round-trip)."""
    return list(await search_cached_cards(session, q))


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
