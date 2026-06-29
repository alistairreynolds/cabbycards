import logging

from app.core.config import get_settings
from app.services.email import (
    ConsoleEmailSender,
    build_verification_url,
    send_verification_email,
)


class _SpySender:
    """Test double capturing what would be sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def test_build_verification_url_points_at_frontend() -> None:
    url = build_verification_url("abc123", get_settings())
    assert url == "http://localhost:5173/verify-email?token=abc123"


async def test_console_sender_logs_recipient_and_subject(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.email"):
        await ConsoleEmailSender().send("player@example.com", "Verify your email", "the body")
    assert "player@example.com" in caplog.text
    assert "Verify your email" in caplog.text


async def test_send_verification_email_includes_the_link() -> None:
    spy = _SpySender()
    settings = get_settings()

    await send_verification_email(spy, "player@example.com", "raw-token-xyz", settings)

    to, _subject, body = spy.sent[0]
    assert to == "player@example.com"
    assert build_verification_url("raw-token-xyz", settings) in body
