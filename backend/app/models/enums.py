import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a native Postgres enum that stores member *values*, not names.

    SQLAlchemy defaults to persisting the member name (e.g. ``APPLE``); we want
    the lowercase value (``apple``). Used by every enum column in the models.

    See: tests/test_enums.py
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class AuthProvider(enum.StrEnum):
    APPLE = "apple"
    GOOGLE = "google"


class CardCondition(enum.StrEnum):
    NEAR_MINT = "nm"
    LIGHTLY_PLAYED = "lp"
    MODERATELY_PLAYED = "mp"
    HEAVILY_PLAYED = "hp"
    DAMAGED = "dmg"


class DeckFormat(enum.StrEnum):
    COMMANDER = "commander"
    STANDARD = "standard"
    PIONEER = "pioneer"
    MODERN = "modern"
    LEGACY = "legacy"
    VINTAGE = "vintage"
    PAUPER = "pauper"
    BRAWL = "brawl"


class DeckBoard(enum.StrEnum):
    """Which list of a deck a card belongs to.

    `command` is the Commander zone (the commander itself); `maybe` is the
    informal maybeboard most deck builders keep alongside main/side.
    """

    MAIN = "main"
    SIDE = "side"
    MAYBE = "maybe"
    COMMAND = "command"
