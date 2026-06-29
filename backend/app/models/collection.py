import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import CardCondition, pg_enum


class CollectionEntry(Base, TimestampMixin):
    """One stack of an owned card in a specific finish and condition.

    A foil Near-Mint and a non-foil Lightly-Played copy of the same card are
    distinct rows — they carry different value and are tracked separately — so
    uniqueness spans (user, card, foil, condition) rather than just (user, card).
    """

    __tablename__ = "collections"

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
    card_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    foil: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    condition: Mapped[CardCondition] = mapped_column(
        pg_enum(CardCondition, "card_condition"),
        nullable=False,
        default=CardCondition.NEAR_MINT,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "card_id", "foil", "condition", name="uq_collections_stack"
        ),
    )
