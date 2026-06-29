from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_email_sender, get_turnstile_verifier
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.services.auth import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidVerificationToken,
    authenticate_user,
    create_verification_token,
    register_user,
    verify_email_token,
)
from app.services.email import EmailSender, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
    verify_turnstile: Callable[[str], Awaitable[bool]] = Depends(get_turnstile_verifier),
) -> TokenResponse:
    """Register with email/password (bot-checked), logging in immediately (soft gate)."""
    if not await verify_turnstile(body.turnstile_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bot check failed")
    try:
        user = await register_user(
            session,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            settings=settings,
            email_sender=email_sender,
        )
    except EmailAlreadyRegistered as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    try:
        user = await authenticate_user(session, email=body.email, password=body.password)
    except InvalidCredentials as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        return await verify_email_token(session, body.token)
    except InvalidVerificationToken as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        ) from exc


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict[str, str]:
    raw_token = await create_verification_token(session, user)
    await send_verification_email(email_sender, user.email, raw_token, settings)
    return {"status": "sent"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
