"""Deck building: legality validation (pure) + allocation orchestration (DB).

Sits on top of the ALI-18 inventory primitives — it never writes holdings or
entries directly, it calls move_holding / set_deck_entry.
"""

from app.models.enums import DeckFormat

# Formats where the deck is a singleton 100-card (incl. commander) list.
_SINGLETON_FORMATS = {DeckFormat.COMMANDER, DeckFormat.BRAWL}
# Scryfall legality states that count as playable.
_LEGAL_STATES = {"legal", "restricted"}
# Boards that count toward the singleton/size rules (the actual deck, not maybe/side).
_COUNTED_BOARDS = {"main", "command"}
_BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _is_basic_land(name: str, type_line: str) -> bool:
    # Basics (and snow basics) are exempt from the singleton rule.
    return name in _BASIC_LAND_NAMES or "Basic" in type_line


def _card_codes(
    row: dict, *, format: DeckFormat, commander_identity: set[str], has_commander: bool
) -> list[str]:
    codes: list[str] = []
    legal_state = row["legalities"].get(format.value)
    if legal_state not in _LEGAL_STATES:
        codes.append("not_format_legal")
    if has_commander and not set(row["color_identity"]).issubset(commander_identity):
        codes.append("off_colour_identity")
    return codes


def deck_violations(
    rows: list[dict],
    *,
    format: DeckFormat,
    commander_identity: set[str],
    has_commander: bool,
) -> dict[str, object]:
    """Return per-card and deck-level legality violation codes.

    Pure — takes plain card facts, no DB. ``rows`` carry name, color_identity,
    type_line, legalities, desired_quantity and board. Deck-level singleton/size
    rules apply only to singleton formats (Commander/Brawl).

    See: tests/test_deck_validation.py
    """
    card_codes = {
        row["name"]: _card_codes(
            row,
            format=format,
            commander_identity=commander_identity,
            has_commander=has_commander,
        )
        for row in rows
    }

    deck_codes: list[str] = []
    if format not in _SINGLETON_FORMATS:
        return {"cards": card_codes, "deck": deck_codes}

    counted = [row for row in rows if row["board"] in _COUNTED_BOARDS]
    total = sum(row["desired_quantity"] for row in counted)
    has_duplicate = any(
        row["desired_quantity"] > 1 and not _is_basic_land(row["name"], row["type_line"])
        for row in counted
    )
    if not has_commander:
        deck_codes.append("no_commander")
    if total != 100:
        deck_codes.append("wrong_size")
    if has_duplicate:
        deck_codes.append("singleton_violation")
    return {"cards": card_codes, "deck": deck_codes}
