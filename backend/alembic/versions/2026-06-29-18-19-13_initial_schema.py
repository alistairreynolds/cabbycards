"""initial schema

Revision ID: 2026_06_29_18_19_13
Revises:
Create Date: 2026-06-29-18-19-13

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2026_06_29_18_19_13"
down_revision: str | None = None
branch_labels = None
depends_on = None

# Enum values mirror the StrEnum values in app/models/enums.py. They are spelled
# out here so the migration is a static snapshot, independent of model code.
_auth_provider = postgresql.ENUM("apple", "google", name="auth_provider", create_type=False)
_card_condition = postgresql.ENUM(
    "nm", "lp", "mp", "hp", "dmg", name="card_condition", create_type=False
)
_deck_format = postgresql.ENUM(
    "commander", "standard", "pioneer", "modern", "legacy", "vintage", "pauper", "brawl",
    name="deck_format", create_type=False,
)
_deck_board = postgresql.ENUM("main", "side", "maybe", "command", name="deck_board", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # Powers fuzzy card-name search via the GIN trigram index on cards.name.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    _auth_provider.create(bind, checkfirst=True)
    _card_condition.create(bind, checkfirst=True)
    _deck_format.create(bind, checkfirst=True)
    _deck_board.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("auth_provider", _auth_provider, nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("auth_provider", "provider_subject", name="uq_users_provider_identity"),
    )

    op.create_table(
        "cards",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scryfall_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("oracle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "name",
            sa.Text(),
            sa.Computed("data ->> 'name'", persisted=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cards"),
        sa.UniqueConstraint("scryfall_id", name="uq_cards_scryfall_id"),
    )
    op.create_index(
        "ix_cards_name_trgm",
        "cards",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index("ix_cards_oracle_id", "cards", ["oracle_id"])

    op.create_table(
        "collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("foil", sa.Boolean(), nullable=False),
        sa.Column("condition", _card_condition, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_collections_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name="fk_collections_card_id_cards", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "user_id", "card_id", "foil", "condition", name="uq_collections_stack"
        ),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])
    op.create_index("ix_collections_card_id", "collections", ["card_id"])

    op.create_table(
        "decks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("format", _deck_format, nullable=False),
        sa.Column("commander_card_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_decks"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_decks_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["commander_card_id"], ["cards.id"], name="fk_decks_commander_card_id_cards", ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_decks_user_id", "decks", ["user_id"])

    op.create_table(
        "deck_cards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("board", _deck_board, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_deck_cards"),
        sa.ForeignKeyConstraint(
            ["deck_id"], ["decks.id"], name="fk_deck_cards_deck_id_decks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name="fk_deck_cards_card_id_cards", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("deck_id", "card_id", "board", name="uq_deck_cards_entry"),
    )
    op.create_index("ix_deck_cards_deck_id", "deck_cards", ["deck_id"])
    op.create_index("ix_deck_cards_card_id", "deck_cards", ["card_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("deck_cards")
    op.drop_table("decks")
    op.drop_table("collections")
    op.drop_table("cards")
    op.drop_table("users")

    _deck_board.drop(bind, checkfirst=True)
    _deck_format.drop(bind, checkfirst=True)
    _card_condition.drop(bind, checkfirst=True)
    _auth_provider.drop(bind, checkfirst=True)
