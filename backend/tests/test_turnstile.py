import httpx

from app.core.config import Settings
from app.services.turnstile import verify_turnstile

_SETTINGS = Settings(database_url="postgresql+asyncpg://unused", turnstile_secret_key="test-secret")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_verify_returns_true_on_success() -> None:
    async with _client(lambda _r: httpx.Response(200, json={"success": True})) as client:
        assert await verify_turnstile("tok", settings=_SETTINGS, client=client) is True


async def test_verify_returns_false_on_failure() -> None:
    failure = {"success": False, "error-codes": ["invalid-input-response"]}
    async with _client(lambda _r: httpx.Response(200, json=failure)) as client:
        assert await verify_turnstile("bad", settings=_SETTINGS, client=client) is False


async def test_verify_returns_false_on_non_200() -> None:
    async with _client(lambda _r: httpx.Response(500, text="boom")) as client:
        assert await verify_turnstile("tok", settings=_SETTINGS, client=client) is False


async def test_verify_posts_secret_and_token() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"success": True})

    async with _client(handler) as client:
        await verify_turnstile("the-token", settings=_SETTINGS, client=client)

    assert "secret=test-secret" in seen["body"]
    assert "response=the-token" in seen["body"]
