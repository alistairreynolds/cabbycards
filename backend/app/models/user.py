import uuid

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # gen_random_uuid() is built into Postgres 13+, no extension required.
        server_default=text("gen_random_uuid()"),
    )

    # The account's canonical identifier; stored lowercased so it stays unique
    # case-insensitively. Auth methods (password, SSO, passkey) hang off
    # auth_identities, so one account can have several.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Soft gate: users can sign in unverified, but verification-gated actions
    # check this flag.
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
