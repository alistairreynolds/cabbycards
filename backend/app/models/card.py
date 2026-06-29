import uuid
from typing import Any

from sqlalchemy import BigInteger, Computed, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Card(Base, TimestampMixin):
    """A single Scryfall card printing, cached locally.

    Relations across the app reference the internal ``id`` (a stable surrogate
    key), never ``scryfall_id`` directly, so the data source stays swappable —
    e.g. switching to Scryfall's bulk-download feed touches only the ingest
    service, not every foreign key.
    """

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Natural key from Scryfall — unique, used for dedup on ingest and lookups.
    scryfall_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)

    # Groups every printing of the same card; the right key for "do I own this
    # card?" matching later, independent of which printing is in a collection.
    oracle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Database-maintained projection of data->>'name' so the trigram index has a
    # plain-text column to ride on and can never drift from the cached blob.
    name: Mapped[str] = mapped_column(
        Text,
        Computed("data->>'name'", persisted=True),
        nullable=False,
    )

    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index(
            "ix_cards_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_cards_oracle_id", "oracle_id"),
    )
