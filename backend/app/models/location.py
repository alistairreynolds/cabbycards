import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import LocationKind, pg_enum


class Location(Base, TimestampMixin):
    """Somewhere a user's cards live: a storage place (binder/box) or a deck.

    A deck is a location of kind ``deck`` with extra attributes in the ``decks``
    table. Every holding points at a location, so "what's in this binder",
    "what's in this deck", and "everything I own" are one query with a filter.
    """

    __tablename__ = "locations"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(
        pg_enum(LocationKind, "location_kind"), nullable=False
    )
