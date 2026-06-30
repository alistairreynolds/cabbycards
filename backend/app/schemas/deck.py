import uuid

from pydantic import BaseModel, Field

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
