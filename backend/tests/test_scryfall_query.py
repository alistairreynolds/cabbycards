"""Pure Scryfall query-builder checks — no network, always run."""

from app.models.enums import DeckFormat
from app.services.scryfall import build_scryfall_query


def test_plain_query_when_no_filters() -> None:
    assert build_scryfall_query("sol ring") == "sol ring"


def test_identity_subset_filter() -> None:
    q = build_scryfall_query("counterspell", identity={"U", "W"}, deck_format=DeckFormat.COMMANDER)
    assert "id<=uw" in q
    assert "legal:commander" in q
    assert q.startswith("counterspell")


def test_empty_identity_means_colourless_only() -> None:
    q = build_scryfall_query("sol ring", identity=set(), deck_format=DeckFormat.COMMANDER)
    assert "id:c" in q


def test_format_only_when_no_identity() -> None:
    q = build_scryfall_query("llanowar", deck_format=DeckFormat.STANDARD)
    assert "legal:standard" in q
    assert "id<=" not in q
    assert "id:c" not in q
