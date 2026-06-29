from app.services.card_search import _escape_like, name_sort_key


def test_escape_like_escapes_percent_and_underscore() -> None:
    assert _escape_like("50%_off") == "50\\%\\_off"


def test_escape_like_escapes_backslash_first() -> None:
    # Backslash must be doubled before the others, or it would re-escape them.
    assert _escape_like("a\\b") == "a\\\\b"


def test_escape_like_leaves_ordinary_names_untouched() -> None:
    assert _escape_like("Sol Ring") == "Sol Ring"


def test_name_sort_key_puts_close_name_match_first() -> None:
    # "sol ring" matched Scryfall full-text noise ("Solemn Offering"); the real
    # card should sort to the top by name relevance.
    names = ["Solemn Offering", "Sol Ring", "Solidarity"]
    ordered = sorted(names, key=lambda n: name_sort_key("sol ring", n))
    assert ordered[0] == "Sol Ring"


def test_name_sort_key_prefix_beats_substring_noise() -> None:
    names = ["Alharu, Solemn Ritualist", "Basri's Solidarity", "Sol Ring"]
    ordered = sorted(names, key=lambda n: name_sort_key("sol ri", n))
    assert ordered[0] == "Sol Ring"


def test_name_sort_key_exact_beats_longer_name_with_same_prefix() -> None:
    names = ["Sol Ring Avatar", "Sol Ring"]
    ordered = sorted(names, key=lambda n: name_sort_key("Sol Ring", n))
    assert ordered[0] == "Sol Ring"
