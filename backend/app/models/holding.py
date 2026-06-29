import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.card import Card
from app.models.enums import CardCondition, pg_enum
from app.models.location import Location


class Holding(Base, TimestampMixin):
    """A quantity of an owned card, in a given finish/condition, at one location.

    The user is implied by the location (``locations.user_id``), so holdings stay
    normalised. The same card in a different finish, condition, or location is a
    separate holding — moving cards just shifts quantity between locations.
    """

    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
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

    # Eager-loaded so a holding can be serialised with its card + location in one go.
    card: Mapped[Card] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "location_id", "card_id", "foil", "condition", name="uq_holdings_stack"
        ),
    )
