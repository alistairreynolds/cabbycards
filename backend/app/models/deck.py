import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import DeckBoard, DeckFormat, pg_enum
from app.models.location import Location


class Deck(Base, TimestampMixin):
    """A deck — a location of kind ``deck`` with deck-specific attributes.

    Its physical contents are the holdings located in it; its intended list (incl.
    cards not yet owned) is held in ``deck_entries``.
    """

    __tablename__ = "decks"

    # 1:1 with a Location (which carries user_id + name). The deck *is* that location.
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    format: Mapped[DeckFormat] = mapped_column(
        pg_enum(DeckFormat, "deck_format"),
        nullable=False,
        default=DeckFormat.COMMANDER,
    )
    # Nullable: only singleton formats (Commander/Brawl) name a commander.
    commander_card_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="RESTRICT"),
        nullable=True,
    )

    location: Mapped[Location] = relationship(lazy="joined")


class DeckEntry(Base, TimestampMixin):
    """A deck's intended card (desired quantity), independent of ownership.

    Owned holdings located in the deck fulfil entries; the shortfall is the
    wantlist (ALI-14).
    """

    __tablename__ = "deck_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decks.location_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    board: Mapped[DeckBoard] = mapped_column(
        pg_enum(DeckBoard, "deck_board"),
        nullable=False,
        default=DeckBoard.MAIN,
    )
    desired_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", "board", name="uq_deck_entries_entry"),
    )
