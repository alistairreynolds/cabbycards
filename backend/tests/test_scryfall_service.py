from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.config import Settings
from app.services.scryfall import ScryfallError, ScryfallService, is_card_stale

_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


def test_is_card_stale_treats_missing_timestamp_as_stale() -> None:
    assert is_card_stale(None, _NOW, ttl_days=14) is True


def test_is_card_stale_false_when_within_ttl() -> None:
    cached_at = _NOW - timedelta(days=13, hours=23)
    assert is_card_stale(cached_at, _NOW, ttl_days=14) is False


def test_is_card_stale_true_once_ttl_exceeded() -> None:
    cached_at = _NOW - timedelta(days=14, seconds=1)
    assert is_card_stale(cached_at, _NOW, ttl_days=14) is True


def _service_with_handler(handler) -> ScryfallService:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.scryfall.test",
    )
    settings = Settings(database_url="postgresql+asyncpg://unused")
    # session is None: these tests exercise only the network layer, not the DB.
    return ScryfallService(session=None, settings=settings, client=client)


async def test_fetch_returns_parsed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "abc", "name": "Sol Ring"})

    async with _service_with_handler(handler) as service:
        payload = await service._fetch("/cards/abc")

    assert payload["name"] == "Sol Ring"


async def test_fetch_raises_scryfall_error_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"object": "error"})

    async with _service_with_handler(handler) as service:
        with pytest.raises(ScryfallError):
            await service._fetch("/cards/missing")


async def test_self_built_client_sets_required_headers() -> None:
    # Scryfall requires a descriptive User-Agent and explicit Accept; verify the
    # service configures them when it builds its own client (no client injected).
    settings = Settings(
        database_url="postgresql+asyncpg://unused",
        scryfall_user_agent="CabbyCards/0.1 (+test)",
    )
    async with ScryfallService(session=None, settings=settings) as service:
        assert "CabbyCards" in service._client.headers["user-agent"]
        assert service._client.headers["accept"] == "application/json"
