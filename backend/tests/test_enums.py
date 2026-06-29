from app.models.enums import (
    AuthIdentityType,
    CardCondition,
    DeckBoard,
    DeckFormat,
    pg_enum,
)


def test_pg_enum_persists_member_values_not_names() -> None:
    # The whole point of the helper: store "password"/"apple", never "PASSWORD".
    enum_type = pg_enum(AuthIdentityType, "auth_identity_type")
    assert enum_type.name == "auth_identity_type"
    emitted = enum_type.values_callable(AuthIdentityType)
    assert sorted(emitted) == ["apple", "google", "passkey", "password"]


def test_card_condition_values_are_short_codes() -> None:
    assert CardCondition.NEAR_MINT == "nm"
    assert [c.value for c in CardCondition] == ["nm", "lp", "mp", "hp", "dmg"]


def test_deck_board_includes_command_zone() -> None:
    assert DeckBoard.COMMAND == "command"
    assert "command" in [b.value for b in DeckBoard]


def test_deck_format_default_set_includes_commander() -> None:
    assert DeckFormat.COMMANDER == "commander"
