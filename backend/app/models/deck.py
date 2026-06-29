import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import DeckBoard, DeckFormat, pg_enum


class Deck(Base, TimestampMixin):
    __tablename__ = "decks"

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


class DeckCard(Base, TimestampMixin):
    __tablename__ = "deck_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    board: Mapped[DeckBoard] = mapped_column(
        pg_enum(DeckBoard, "deck_board"),
        nullable=False,
        default=DeckBoard.MAIN,
    )

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", "board", name="uq_deck_cards_entry"),
    )
