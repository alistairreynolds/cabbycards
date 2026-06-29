import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_scryfall_service
from app.core.db import get_session
from app.models.user import User
from app.schemas.collection import (
    AddCardRequest,
    HoldingOut,
    LocationCreate,
    LocationOut,
    MoveCardRequest,
)
from app.services.inventory import (
    InsufficientQuantity,
    add_holding,
    create_storage_location,
    ensure_default_location,
    get_owned_holding,
    get_owned_location,
    list_holdings,
    list_locations,
    move_holding,
    remove_holding,
)
from app.services.scryfall import ScryfallError, ScryfallService

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("/locations", response_model=list[LocationOut])
async def get_locations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LocationOut]:
    await ensure_default_location(session, user)
    return list(await list_locations(session, user))


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LocationOut:
    return await create_storage_location(session, user, body.name)


@router.get("", response_model=list[HoldingOut])
async def get_collection(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HoldingOut]:
    await ensure_default_location(session, user)
    return list(await list_holdings(session, user))


@router.post("/add", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
async def add_card(
    body: AddCardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    scryfall: ScryfallService = Depends(get_scryfall_service),
) -> HoldingOut:
    location = await get_owned_location(session, user, body.location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Location not found")
    try:
        card = await scryfall.get_card(body.scryfall_id)
    except ScryfallError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Card not found") from exc

    holding = await add_holding(
        session,
        location=location,
        card_id=card.id,
        quantity=body.quantity,
        foil=body.foil,
        condition=body.condition,
    )
    # Re-fetch so card + location relationships are eager-loaded for serialisation.
    return await get_owned_holding(session, user, holding.id)


@router.post("/move")
async def move_card(
    body: MoveCardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    source = await get_owned_location(session, user, body.from_location_id)
    destination = await get_owned_location(session, user, body.to_location_id)
    if source is None or destination is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Location not found")
    try:
        await move_holding(
            session,
            from_location=source,
            to_location=destination,
            card_id=body.card_id,
            quantity=body.quantity,
            foil=body.foil,
            condition=body.condition,
        )
    except InsufficientQuantity as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Not enough copies at the source location"
        ) from exc
    return {"status": "ok"}


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    holding = await get_owned_holding(session, user, holding_id)
    if holding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await remove_holding(session, holding)
