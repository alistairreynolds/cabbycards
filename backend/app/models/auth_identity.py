import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import AuthIdentityType, pg_enum


class AuthIdentity(Base, TimestampMixin):
    """One authentication method belonging to a user.

    `password` rows carry a `password_hash`; SSO rows (`apple`/`google`) carry a
    `provider_subject`. A user has at most one identity of each type.
    """

    __tablename__ = "auth_identities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[AuthIdentityType] = mapped_column(
        pg_enum(AuthIdentityType, "auth_identity_type"), nullable=False
    )

    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_auth_identities_user_type"),
        # SSO subjects must be globally unique per provider; password rows have a
        # NULL subject and are excluded via the partial index.
        Index(
            "uq_auth_identities_provider_subject",
            "type",
            "provider_subject",
            unique=True,
            postgresql_where=text("provider_subject IS NOT NULL"),
        ),
    )
