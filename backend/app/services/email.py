import logging
from typing import Protocol

from app.core.config import Settings

_logger = logging.getLogger("app.email")


class EmailSender(Protocol):
    """Sends an email. Implementations: ConsoleEmailSender (dev); SMTP later."""

    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Dev email backend — logs the message instead of sending it.

    See: tests/test_email.py
    """

    async def send(self, to: str, subject: str, body: str) -> None:
        _logger.info("EMAIL to=%s subject=%s\n%s", to, subject, body)


def build_verification_url(raw_token: str, settings: Settings) -> str:
    """Build the frontend link a user clicks to verify their email.

    See: tests/test_email.py
    """
    return f"{settings.frontend_base_url}/verify-email?token={raw_token}"


async def send_verification_email(
    sender: EmailSender, to: str, raw_token: str, settings: Settings
) -> None:
    """Compose and send the email-verification message.

    See: tests/test_email.py
    """
    url = build_verification_url(raw_token, settings)
    body = (
        "Welcome to CabbyCards!\n\n"
        f"Please verify your email by opening this link:\n{url}\n\n"
        "If you didn't sign up, you can ignore this message."
    )
    await sender.send(to, "Verify your CabbyCards email", body)


def build_reset_url(raw_token: str, settings: Settings) -> str:
    """Build the frontend link a user clicks to reset their password.

    See: tests/test_email.py
    """
    return f"{settings.frontend_base_url}/reset-password?token={raw_token}"


async def send_password_reset_email(
    sender: EmailSender, to: str, raw_token: str, settings: Settings
) -> None:
    """Compose and send the password-reset message.

    See: tests/test_email.py
    """
    url = build_reset_url(raw_token, settings)
    body = (
        "Someone (hopefully you) asked to reset your CabbyCards password.\n\n"
        f"Reset it here:\n{url}\n\n"
        "If you didn't request this, you can ignore this message — your password "
        "won't change."
    )
    await sender.send(to, "Reset your CabbyCards password", body)
