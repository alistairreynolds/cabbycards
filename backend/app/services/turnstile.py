import httpx

from app.core.config import Settings, get_settings


async def verify_turnstile(
    token: str,
    *,
    remote_ip: str | None = None,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Verify a Cloudflare Turnstile token server-side.

    Returns False on any failure (bad token, non-200, malformed body) rather than
    raising — the caller treats False as "rejected". Client is injectable for tests.

    See: tests/test_turnstile.py
    """
    settings = settings or get_settings()
    data = {"secret": settings.turnstile_secret_key, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        response = await client.post(settings.turnstile_verify_url, data=data)
        if response.status_code != httpx.codes.OK:
            return False
        return bool(response.json().get("success", False))
    finally:
        if owns_client:
            await client.aclose()
