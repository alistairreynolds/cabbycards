"""Pure deck-legality checks — no DB, always run."""

from app.models.enums import DeckBoard, DeckFormat
from app.services.deck_builder import deck_violations


def _card(name, *, identity=(), type_line="Creature", legal="legal", qty=1, board=DeckBoard.MAIN):
    return {
        "name": name,
        "color_identity": list(identity),
        "type_line": type_line,
        "legalities": {"commander": legal},
        "desired_quantity": qty,
        "board": board.value,
    }


def test_off_colour_identity_is_flagged() -> None:
    rows = [_card("Lightning Bolt", identity=("R",))]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U", "W"}, has_commander=True
    )
    assert "off_colour_identity" in result["cards"]["Lightning Bolt"]


def test_in_identity_card_is_clean() -> None:
    rows = [_card("Counterspell", identity=("U",))]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U", "W"}, has_commander=True
    )
    assert result["cards"].get("Counterspell", []) == []


def test_not_format_legal_is_flagged() -> None:
    rows = [_card("Black Lotus", legal="banned")]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=True
    )
    assert "not_format_legal" in result["cards"]["Black Lotus"]


def test_singleton_violation_for_non_basic_duplicate() -> None:
    rows = [_card("Sol Ring", identity=(), type_line="Artifact", qty=2)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=True
    )
    assert "singleton_violation" in result["deck"]


def test_basic_land_duplicates_are_allowed() -> None:
    rows = [_card("Island", identity=("U",), type_line="Basic Land — Island", qty=30)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity={"U"}, has_commander=True
    )
    assert "singleton_violation" not in result["deck"]


def test_no_commander_and_wrong_size_for_commander_deck() -> None:
    rows = [_card("Island", identity=("U",), type_line="Basic Land", qty=10)]
    result = deck_violations(
        rows, format=DeckFormat.COMMANDER, commander_identity=set(), has_commander=False
    )
    assert "no_commander" in result["deck"]
    assert "wrong_size" in result["deck"]


def test_standard_format_skips_commander_only_rules() -> None:
    rows = [_card("Llanowar Elves", identity=("G",), legal="legal", qty=4)]
    rows[0]["legalities"] = {"standard": "legal"}
    result = deck_violations(
        rows, format=DeckFormat.STANDARD, commander_identity=set(), has_commander=False
    )
    assert result["deck"] == []
    assert result["cards"].get("Llanowar Elves", []) == []
