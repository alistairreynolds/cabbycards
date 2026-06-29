from app.services.card_search import _escape_like


def test_escape_like_escapes_percent_and_underscore() -> None:
    assert _escape_like("50%_off") == "50\\%\\_off"


def test_escape_like_escapes_backslash_first() -> None:
    # Backslash must be doubled before the others, or it would re-escape them.
    assert _escape_like("a\\b") == "a\\\\b"


def test_escape_like_leaves_ordinary_names_untouched() -> None:
    assert _escape_like("Sol Ring") == "Sol Ring"
