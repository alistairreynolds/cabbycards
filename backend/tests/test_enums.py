from app.models.enums import (
    AuthProvider,
    CardCondition,
    DeckBoard,
    DeckFormat,
    pg_enum,
)


def test_pg_enum_persists_member_values_not_names() -> None:
    # The whole point of the helper: store "apple"/"google", never "APPLE".
    enum_type = pg_enum(AuthProvider, "auth_provider")
    assert enum_type.name == "auth_provider"
    emitted = enum_type.values_callable(AuthProvider)
    assert sorted(emitted) == ["apple", "google"]


def test_card_condition_values_are_short_codes() -> None:
    assert CardCondition.NEAR_MINT == "nm"
    assert [c.value for c in CardCondition] == ["nm", "lp", "mp", "hp", "dmg"]


def test_deck_board_includes_command_zone() -> None:
    assert DeckBoard.COMMAND == "command"
    assert "command" in [b.value for b in DeckBoard]


def test_deck_format_default_set_includes_commander() -> None:
    assert DeckFormat.COMMANDER == "commander"
