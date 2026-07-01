import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.card import Card
from app.models.enums import DeckFormat

# Scryfall asks clients to leave 50-100ms between requests (a ~10 req/s ceiling).
# Going faster risks an HTTP 429 and, repeatedly, an IP ban.
_REQUEST_DELAY_SECONDS = 0.1


class ScryfallError(RuntimeError):
    """Raised when Scryfall returns an error or an unexpected payload."""


def build_scryfall_query(
    terms: str, *, identity: set[str] | None = None, deck_format: DeckFormat | None = None
) -> str:
    """Append colour-identity + format-legality filters to a Scryfall query.

    ``identity`` is a set of single-letter colours (the commander's identity); an
    empty set means a colourless commander, so only colourless cards are legal
    (``id:c``). A non-empty set uses Scryfall's subset operator (``id<=wu``).
    ``None`` adds no identity filter.

    See: tests/test_scryfall_query.py
    """
    parts = [terms.strip()]
    if identity is not None:
        if identity:
            parts.append(f"id<={''.join(sorted(c.lower() for c in identity))}")
        else:
            parts.append("id:c")
    if deck_format is not None:
        parts.append(f"legal:{deck_format.value}")
    return " ".join(part for part in parts if part)


def is_card_stale(cached_at: datetime | None, now: datetime, ttl_days: int) -> bool:
    """Whether a cached card should be re-fetched.

    Pure and time-injected (``now`` is a parameter) so the freshness policy can
    be tested without patching the clock.

    See: tests/test_scryfall_service.py
    """
    if cached_at is None:
        return True
    return now - cached_at > timedelta(days=ttl_days)


class ScryfallService:
    """Ingest/resolve layer between Scryfall and the local ``cards`` table.

    Callers get back internal :class:`Card` rows; the Scryfall id never leaks
    into the rest of the app's relations. The HTTP client is injectable so tests
    can supply an ``httpx.MockTransport`` instead of reaching the network.

    See: tests/test_scryfall_service.py
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._settings.scryfall_base_url,
            headers={
                # Scryfall requires a descriptive User-Agent and explicit Accept.
                "User-Agent": self._settings.scryfall_user_agent,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(10.0),
        )

    async def aclose(self) -> None:
        # Only close clients we created; an injected one is the caller's to manage.
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "ScryfallService":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def get_card(self, scryfall_id: uuid.UUID, *, now: datetime | None = None) -> Card:
        """Return a card, serving from cache unless missing or stale."""
        now = now or datetime.now(UTC)
        cached = await self._session.scalar(
            select(Card).where(Card.scryfall_id == scryfall_id)
        )
        if cached is not None and not is_card_stale(
            cached.updated_at, now, self._settings.card_cache_ttl_days
        ):
            return cached

        data = await self._fetch(f"/cards/{scryfall_id}")
        return await self._ingest(data)

    async def search(self, query: str) -> list[Card]:
        """Search Scryfall and cache every returned card.

        Returns the first page only; deep pagination is a later concern.
        """
        payload = await self._fetch("/cards/search", params={"q": query})
        results: list[Card] = []
        for data in payload.get("data", []):
            results.append(await self._ingest(data))
        return results

    async def search_cards(
        self,
        query: str,
        *,
        identity: set[str] | None = None,
        deck_format: DeckFormat | None = None,
    ) -> list[Card]:
        """Search Scryfall with colour-identity + format filters applied.

        See: tests/test_scryfall_service.py
        """
        return await self.search(
            build_scryfall_query(query, identity=identity, deck_format=deck_format)
        )

    async def list_printings(self, oracle_id: uuid.UUID) -> list[Card]:
        """Every printing of a card (one row per set), in release-date order, all cached.

        See: tests/test_scryfall_service.py
        """
        payload = await self._fetch(
            "/cards/search",
            params={"q": f"oracleid:{oracle_id}", "unique": "prints", "order": "released"},
        )
        return [await self._ingest(data) for data in payload.get("data", [])]

    async def _fetch(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await asyncio.sleep(_REQUEST_DELAY_SECONDS)
        response = await self._client.get(path, params=params)
        if response.status_code == httpx.codes.NOT_FOUND:
            raise ScryfallError(f"Scryfall returned 404 for {path}")
        response.raise_for_status()
        return response.json()

    async def _ingest(self, data: dict[str, Any]) -> Card:
        """Upsert a Scryfall card payload into the local table by scryfall_id.

        On conflict we refresh the blob and bump updated_at, so re-ingesting an
        existing card simply renews its cache freshness.
        """
        oracle_id = data.get("oracle_id")
        statement = pg_insert(Card).values(
            scryfall_id=uuid.UUID(data["id"]),
            oracle_id=uuid.UUID(oracle_id) if oracle_id else None,
            data=data,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[Card.scryfall_id],
            set_={
                "data": statement.excluded.data,
                "oracle_id": statement.excluded.oracle_id,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(statement)
        await self._session.commit()

        card = await self._session.scalar(
            select(Card).where(Card.scryfall_id == uuid.UUID(data["id"]))
        )
        if card is None:
            raise ScryfallError("Card vanished immediately after upsert")
        return card
