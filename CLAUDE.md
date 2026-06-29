# CabbyCards — Project Guide

MTG collection & deck management web app with a companion iOS scanning app.
**Commander is the primary use case** — colour-identity filtering and commander
legality are first-class concerns, not afterthoughts.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Vue 3 + Vite + Pinia (SPA, no SSR/Nuxt) |
| Backend | Python ≥3.12, FastAPI, SQLAlchemy 2.0 **async** |
| DB | PostgreSQL (default for everything), `asyncpg` driver |
| Migrations | Alembic (async `env.py`); datestamp filenames `YYYY-MM-DD-HH-MM-SS_slug.py` (rev id uses `_` — Alembic bars `-`) |
| Auth | Apple + Google SSO via Authlib → backend issues session JWTs (`PyJWT`) |
| Card data | Scryfall REST API, cached locally in JSONB |
| iOS | Capacitor wrapping the Vue app + native Swift Vision scanner |
| Hosting | AWS (existing infra) |
| Py tooling | `uv` (pyproject + `uv.lock`) |
| Local DB | Docker Compose (`postgres:16-alpine`, host port **5433**) |

## Monorepo layout

```
backend/   FastAPI app, models, services, Alembic    ← built
frontend/  Vue 3 SPA                                  ← placeholder
ios/       Capacitor + Swift scanner                  ← placeholder
docker-compose.yml   local Postgres
```

Backend internals: `app/core` (config, db), `app/models` (one file per
aggregate), `app/schemas` (Pydantic), `app/services` (Scryfall ingest, card
search), `app/api/routes`.

## Key architecture decisions

### Internal `cards` table, not vendor-locked `scryfall_id`
The original spec had a `card_cache` keyed by `scryfall_id`. We replaced it with
a `cards` table carrying its own internal **`id` (BigInteger identity)** plus
`scryfall_id` (unique) and `oracle_id`. **All relations reference `cards.id`**,
never `scryfall_id`. This is the surrogate-key + natural-key split: foreign keys
stay stable, and swapping the data source (e.g. Scryfall's **bulk-download**
feed) touches only the ingest service. `oracle_id` is stored now so future
"do I own this card?" matching can work at the oracle (printing-agnostic) level.

### Fuzzy search via a generated column + pg_trgm
`cards.name` is `GENERATED ALWAYS AS (data->>'name') STORED`, with a GIN
`gin_trgm_ops` index. Trigram indexes need a plain-text column; generating it
from the JSONB blob keeps it permanently in sync. The `pg_trgm` extension is
enabled **inside the initial migration** (portable to RDS), not via a Docker
init script.

### Collection uniqueness spans finish & condition
`collections` is unique on `(user_id, card_id, foil, condition)` — a foil NM and
a non-foil LP of the same card are genuinely different stacks with different value.

### Enums are native Postgres enums storing values, not names
SQLAlchemy defaults to persisting enum *member names* (`APPLE`). The
`pg_enum()` helper in `app/models/enums.py` forces *values* (`apple`). The
initial migration spells the values out literally so it stays a static snapshot.

### Scryfall politeness
`app/services/scryfall.py` sends a descriptive `User-Agent` + `Accept` header and
leaves ~100ms between requests (Scryfall's ~10 req/s guidance). Cards re-fetch
when missing or older than `CARD_CACHE_TTL_DAYS` (default 14). The HTTP client is
injectable for testing (`httpx.MockTransport`).

### Local search ranking — tiered relevance
`search_cached_cards()` ranks results **exact → prefix → substring → trigram-fuzzy**
(lower tier wins), ordered by similarity then name within a tier. The first three
tiers **bypass** the similarity threshold, so short prefixes (e.g. "sol") aren't
filtered out by trigram scoring. LIKE wildcards in the query are escaped
(`_escape_like`). Tune the tiers/threshold there as the search UX evolves.

## Conventions (apply to all code)

- **British English** in identifiers/comments (`colour`, not `color`).
- Early returns over deep nesting; **no nested ternaries**.
- Private methods/attributes prefixed `_`.
- Comments explain **why**, not what. No narrating-the-obvious comments.
- **Every function has a test**, and references it with a `See: <test file>` line
  in its docstring. Python tests are co-located under `backend/tests/` (pytest).
- Reuse before rebuild (AHA) — grep for an existing helper before writing new logic.
- Mark deprecations explicitly.

## Commands

```bash
docker compose up -d db                          # Postgres :5433
cd backend && uv sync                            # install deps
uv run alembic upgrade head                      # apply schema
uv run uvicorn app.main:app --reload             # serve (/docs)
uv run pytest                                    # hermetic tests
uv run ruff check .                              # lint
CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_integration_db.py  # DB round-trip
uv run alembic revision --autogenerate -m "msg"  # new migration
```

## Feature roadmap (priority order — slices)

1. ✅ Scaffold + DB models + Scryfall cache service *(this slice)*
2. ⬜ Auth — Apple + Google SSO → session JWT
3. ⬜ Card search endpoints polish (pagination, ranking)
4. ⬜ Collection management (add/remove, quantity, foil, condition)
5. ⬜ Deck building — commander, colour-identity & format-legality filtering
6. ⬜ "Owned only" filter in deck builder (resolve via `oracle_id`)
7. ⬜ Missing-cards export — Cardmarket wantlist (`<qty> <name>` per line)
8. ⬜ iOS — Capacitor shell + native Swift Vision scanner bridge
9. ⬜ Vue frontend

## Git

Personal project — repo lives on the owner's **personal GitHub account**
(private). `gh` is not installed locally; create the remote manually or install
`gh` first. Nothing is pushed automatically.
