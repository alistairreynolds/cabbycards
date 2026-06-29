from collections.abc import Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card

# pg_trgm similarity below this counts as "no match" for the *fuzzy* tier. 0.3 is
# Postgres' default for the `%` operator; lower is fuzzier, higher is stricter.
DEFAULT_SIMILARITY_THRESHOLD = 0.3


def name_sort_key(query: str, name: str) -> tuple[int, int, str]:
    """Sort key ranking a card name by how well it matches a typed query.

    Tiers (lower = better): exact match, name starts with the query, query
    appears anywhere, else. Ties break by shorter name then alphabetically.
    Used to re-rank Scryfall search results, which otherwise come back by
    full-text relevance (so "sol ring" surfaces "Solemn Offering").

    See: tests/test_card_search.py
    """
    q = query.strip().lower()
    n = name.lower()
    if n == q:
        tier = 0
    elif n.startswith(q):
        tier = 1
    elif q in n:
        tier = 2
    else:
        tier = 3
    return (tier, len(name), n)


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards so user input is matched literally, not as a pattern.

    Without this, a query containing % or _ would behave as a wildcard.

    See: tests/test_card_search.py
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_cached_cards(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Sequence[Card]:
    """Fuzzy-search locally cached card names, ranked by relevance.

    Tiers (best first): exact name, prefix, substring, then trigram-fuzzy. The
    first three are deliberate matches and bypass the similarity threshold — a
    short prefix like "sol" scores low on trigram similarity yet is exactly what
    the user typed, so it must not be filtered out. Within a tier, results are
    ordered by trigram similarity, then alphabetically.

    See: tests/test_integration_db.py
    """
    normalised = query.strip()
    if not normalised:
        return []

    like_term = _escape_like(normalised)
    similarity = func.similarity(Card.name, normalised)
    rank = case(
        (func.lower(Card.name) == normalised.lower(), 0),
        (Card.name.ilike(f"{like_term}%", escape="\\"), 1),
        (Card.name.ilike(f"%{like_term}%", escape="\\"), 2),
        else_=3,
    )

    statement = (
        select(Card)
        .where(or_(rank < 3, similarity >= threshold))
        .order_by(rank.asc(), similarity.desc(), Card.name.asc())
        .limit(limit)
    )
    return (await session.scalars(statement)).all()
