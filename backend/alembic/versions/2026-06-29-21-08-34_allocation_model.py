"""allocation model: locations + holdings + deck_entries

Replaces the standalone collections/decks/deck_cards tables with the unified
allocation model (ALI-18): one collection of holdings, each at a location; a
deck is a location with an intended deck_entries list.

Revision ID: 2026_06_29_21_08_34
Revises: 2026_06_29_20_52_54
Create Date: 2026-06-29-21-08-34

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2026_06_29_21_08_34"
down_revision: str | None = "2026_06_29_20_52_54"
branch_labels = None
depends_on = None

_location_kind = postgresql.ENUM("storage", "deck", name="location_kind", create_type=False)

# Reused enums (already created by the initial migration).
_card_condition = postgresql.ENUM(
    "nm", "lp", "mp", "hp", "dmg", name="card_condition", create_type=False
)
_deck_format = postgresql.ENUM(
    "commander", "standard", "pioneer", "modern", "legacy", "vintage", "pauper", "brawl",
    name="deck_format", create_type=False,
)
_deck_board = postgresql.ENUM(
    "main", "side", "maybe", "command", name="deck_board", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # Drop the old siloed tables (nothing is built on them yet).
    op.drop_table("deck_cards")
    op.drop_table("collections")
    op.drop_table("decks")

    _location_kind.create(bind, checkfirst=True)

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", _location_kind, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_locations_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_locations_user_id", "locations", ["user_id"])

    op.create_table(
        "decks",
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", _deck_format, nullable=False),
        sa.Column("commander_card_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("location_id", name="pk_decks"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name="fk_decks_location_id_locations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commander_card_id"], ["cards.id"], name="fk_decks_commander_card_id_cards", ondelete="RESTRICT"),
    )

    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("foil", sa.Boolean(), nullable=False),
        sa.Column("condition", _card_condition, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_holdings"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name="fk_holdings_location_id_locations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], name="fk_holdings_card_id_cards", ondelete="RESTRICT"),
        sa.UniqueConstraint("location_id", "card_id", "foil", "condition", name="uq_holdings_stack"),
    )
    op.create_index("ix_holdings_location_id", "holdings", ["location_id"])
    op.create_index("ix_holdings_card_id", "holdings", ["card_id"])

    op.create_table(
        "deck_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("board", _deck_board, nullable=False),
        sa.Column("desired_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_deck_entries"),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.location_id"], name="fk_deck_entries_deck_id_decks", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], name="fk_deck_entries_card_id_cards", ondelete="RESTRICT"),
        sa.UniqueConstraint("deck_id", "card_id", "board", name="uq_deck_entries_entry"),
    )
    op.create_index("ix_deck_entries_deck_id", "deck_entries", ["deck_id"])
    op.create_index("ix_deck_entries_card_id", "deck_entries", ["card_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("deck_entries")
    op.drop_table("holdings")
    op.drop_table("decks")
    # Drop the table before the enum type it depends on.
    op.drop_table("locations")
    _location_kind.drop(bind, checkfirst=True)

    # Recreate the original siloed tables (pre-ALI-18 shape).
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("foil", sa.Boolean(), nullable=False),
        sa.Column("condition", _card_condition, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_collections_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], name="fk_collections_card_id_cards", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "card_id", "foil", "condition", name="uq_collections_stack"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])
    op.create_index("ix_collections_card_id", "collections", ["card_id"])

    op.create_table(
        "decks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("format", _deck_format, nullable=False),
        sa.Column("commander_card_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_decks"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_decks_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commander_card_id"], ["cards.id"], name="fk_decks_commander_card_id_cards", ondelete="RESTRICT"),
    )
    op.create_index("ix_decks_user_id", "decks", ["user_id"])

    op.create_table(
        "deck_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("board", _deck_board, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_deck_cards"),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], name="fk_deck_cards_deck_id_decks", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], name="fk_deck_cards_card_id_cards", ondelete="RESTRICT"),
        sa.UniqueConstraint("deck_id", "card_id", "board", name="uq_deck_cards_entry"),
    )
    op.create_index("ix_deck_cards_deck_id", "deck_cards", ["deck_id"])
    op.create_index("ix_deck_cards_card_id", "deck_cards", ["card_id"])
