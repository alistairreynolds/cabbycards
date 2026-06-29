from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    generate_verification_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.auth_identity import AuthIdentity
from app.models.email_verification_token import EmailVerificationToken
from app.models.enums import AuthIdentityType
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email import (
    EmailSender,
    send_password_reset_email,
    send_verification_email,
)

_VERIFICATION_TTL_HOURS = 24
_RESET_TTL_HOURS = 1


class AuthError(Exception):
    """Base class for auth failures."""


class EmailAlreadyRegistered(AuthError):
    """Registration attempted with an email that already has an account."""


class InvalidCredentials(AuthError):
    """Login failed — unknown email or wrong password."""


class InvalidVerificationToken(AuthError):
    """Email-verification token is unknown, already used, or expired."""


class InvalidResetToken(AuthError):
    """Password-reset token is unknown, already used, or expired."""


def _normalise_email(email: str) -> str:
    # Lowercase + trim so the unique constraint is effectively case-insensitive.
    return email.strip().lower()


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str | None,
    settings: Settings,
    email_sender: EmailSender,
) -> User:
    """Create a user + password identity, then email a verification link.

    See: tests/test_auth_service.py
    """
    normalised = _normalise_email(email)
    existing = await session.scalar(select(User).where(User.email == normalised))
    if existing is not None:
        raise EmailAlreadyRegistered(normalised)

    user = User(email=normalised, display_name=display_name)
    session.add(user)
    await session.flush()  # populate user.id before attaching the identity

    session.add(
        AuthIdentity(
            user_id=user.id,
            type=AuthIdentityType.PASSWORD,
            password_hash=hash_password(password),
        )
    )
    await session.commit()

    raw_token = await create_verification_token(session, user)
    await send_verification_email(email_sender, normalised, raw_token, settings)
    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    """Return the user for valid email+password, else raise InvalidCredentials.

    See: tests/test_auth_service.py
    """
    normalised = _normalise_email(email)
    user = await session.scalar(select(User).where(User.email == normalised))
    if user is None:
        raise InvalidCredentials()

    identity = await session.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.type == AuthIdentityType.PASSWORD,
        )
    )
    if identity is None or identity.password_hash is None:
        raise InvalidCredentials()
    if not verify_password(password, identity.password_hash):
        raise InvalidCredentials()
    return user


async def create_verification_token(
    session: AsyncSession,
    user: User,
    *,
    ttl_hours: int = _VERIFICATION_TTL_HOURS,
    now: datetime | None = None,
) -> str:
    """Persist a single-use email-verification token, returning the raw value.

    See: tests/test_auth_service.py
    """
    now = now or datetime.now(UTC)
    raw, token_hash = generate_verification_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(hours=ttl_hours),
        )
    )
    await session.commit()
    return raw


async def verify_email_token(
    session: AsyncSession, raw_token: str, *, now: datetime | None = None
) -> User:
    """Consume a verification token and mark the user's email verified.

    See: tests/test_auth_service.py
    """
    now = now or datetime.now(UTC)
    token = await session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(raw_token)
        )
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise InvalidVerificationToken()

    user = await session.get(User, token.user_id)
    if user is None:
        raise InvalidVerificationToken()

    user.email_verified = True
    token.used_at = now
    await session.commit()
    return user


async def create_password_reset_token(
    session: AsyncSession,
    user: User,
    *,
    ttl_hours: int = _RESET_TTL_HOURS,
    now: datetime | None = None,
) -> str:
    """Persist a single-use password-reset token, returning the raw value.

    See: tests/test_password_reset_service.py
    """
    now = now or datetime.now(UTC)
    raw, token_hash = generate_verification_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(hours=ttl_hours),
        )
    )
    await session.commit()
    return raw


async def request_password_reset(
    session: AsyncSession,
    *,
    email: str,
    settings: Settings,
    email_sender: EmailSender,
    now: datetime | None = None,
) -> None:
    """Email a reset link if the address has a password account.

    Always returns without error and sends nothing for unknown addresses, so
    callers can't use it to discover which emails are registered.

    See: tests/test_password_reset_service.py
    """
    normalised = _normalise_email(email)
    user = await session.scalar(select(User).where(User.email == normalised))
    if user is None:
        return

    identity = await session.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.type == AuthIdentityType.PASSWORD,
        )
    )
    if identity is None:
        return

    raw_token = await create_password_reset_token(session, user, now=now)
    await send_password_reset_email(email_sender, normalised, raw_token, settings)


async def reset_password(
    session: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
    now: datetime | None = None,
) -> User:
    """Consume a reset token and set a new password on the password identity.

    See: tests/test_password_reset_service.py
    """
    now = now or datetime.now(UTC)
    token = await session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(raw_token)
        )
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise InvalidResetToken()

    identity = await session.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == token.user_id,
            AuthIdentity.type == AuthIdentityType.PASSWORD,
        )
    )
    if identity is None:
        raise InvalidResetToken()

    identity.password_hash = hash_password(new_password)
    token.used_at = now
    await session.commit()

    user = await session.get(User, token.user_id)
    if user is None:
        raise InvalidResetToken()
    return user
