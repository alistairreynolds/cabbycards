import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import TokenError, decode_access_token
from app.models.deck import Deck
from app.models.location import Location
from app.models.user import User
from app.services.email import ConsoleEmailSender, EmailSender
from app.services.scryfall import ScryfallService
from app.services.turnstile import verify_turnstile

_bearer = HTTPBearer(auto_error=False)


async def get_scryfall_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[ScryfallService]:
    """Provide a request-scoped Scryfall service with a managed HTTP client."""
    async with ScryfallService(session) as service:
        yield service


def get_email_sender() -> EmailSender:
    """The active email backend. Only the console sender exists today (no AWS/SES)."""
    return ConsoleEmailSender()


def get_turnstile_verifier() -> Callable[[str], Awaitable[bool]]:
    """Return the Turnstile verifier. A dependency so tests can override it and
    avoid a network call to Cloudflare."""
    return verify_turnstile


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the user from a Bearer session JWT, or raise 401.

    See: tests/test_auth_api.py
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        subject = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(subject)
    except (TokenError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


async def get_owned_deck(session: AsyncSession, user: User, deck_id: uuid.UUID) -> Deck | None:
    """Fetch a deck only if its location belongs to the user (else None).

    See: tests/test_decks_api.py
    """
    return await session.scalar(
        select(Deck)
        .join(Location, Deck.location_id == Location.id)
        .where(Deck.location_id == deck_id, Location.user_id == user.id)
    )
