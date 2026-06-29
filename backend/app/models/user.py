import uuid

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import AuthProvider, pg_enum


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # gen_random_uuid() is built into Postgres 13+, no extension required.
        server_default=text("gen_random_uuid()"),
    )

    # Apple can withhold the real address (private relay), so email is optional.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    auth_provider: Mapped[AuthProvider] = mapped_column(
        pg_enum(AuthProvider, "auth_provider"), nullable=False
    )
    # The provider's stable subject identifier (Apple/Google `sub` claim).
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("auth_provider", "provider_subject", name="uq_users_provider_identity"),
    )
