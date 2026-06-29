import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CardCondition, LocationKind
from app.schemas.card import CardOut


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: LocationKind


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    quantity: int
    foil: bool
    condition: CardCondition
    card: CardOut


class AddCardRequest(BaseModel):
    scryfall_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)
    foil: bool = False
    condition: CardCondition = CardCondition.NEAR_MINT


class MoveCardRequest(BaseModel):
    card_id: int
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)
    foil: bool = False
    condition: CardCondition = CardCondition.NEAR_MINT
