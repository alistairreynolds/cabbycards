import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scryfall_id: uuid.UUID
    oracle_id: uuid.UUID | None
    name: str
    # The full Scryfall blob — the frontend renders images, mana cost, etc. from it.
    data: dict[str, Any]
