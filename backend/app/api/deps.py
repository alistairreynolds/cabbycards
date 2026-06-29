from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.services.scryfall import ScryfallService


async def get_scryfall_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[ScryfallService]:
    """Provide a request-scoped Scryfall service with a managed HTTP client."""
    async with ScryfallService(session) as service:
        yield service
