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
| Auth | Email/password (Argon2id) + passkeys + Apple/Google SSO; session JWTs (`PyJWT`); Cloudflare Turnstile on registration |
| Card data | Scryfall REST API, cached locally in JSONB |
| iOS | Capacitor wrapping the Vue app + native Swift Vision scanner |
| Hosting | **No AWS** — hobbyist/free tooling for now; hosting TBD. Email via SMTP (free provider) when needed, not SES |
| Py tooling | `uv` (pyproject + `uv.lock`) |
| Local DB | Docker Compose (`postgres:16-alpine`, host port **5433**) |

## Monorepo layout

```
backend/   FastAPI app, models, services, Alembic    ← built
frontend/  Vue 3 SPA                                  ← placeholder
ios/       Capacitor + Swift scanner                  ← placeholder
docker-compose.yml   local Postgres
```

Backend internals: `app/core` (config, db, **security** = Argon2 + JWT + token
hashing), `app/models` (one file per aggregate), `app/schemas` (Pydantic),
`app/services` (Scryfall ingest, card search, **auth**, **turnstile**, **email**),
`app/api/routes` (cards, **auth**) + `app/api/deps.py` (current-user, etc.).

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

### Auth — identity model (ALI-5, slice 1 built: email/password)
One account, many login methods. `users` (email-centric, `email_verified`) +
`auth_identities` (type `password`|`apple`|`google`|`passkey`; one per user per
type, partial-unique SSO subject) + `email_verification_tokens` (we store the
SHA-256 hash, email the raw token). Passwords use **Argon2id**. Sessions are a
signed **JWT** (`app/core/security.py`). Registration is gated by **Cloudflare
Turnstile** (dev uses Cloudflare's always-pass test key); the verifier is a
FastAPI dependency so tests override it instead of calling the network. Email
verification is a **soft gate** — users log in immediately; verification-gated
actions check `email_verified`. Email goes through an `EmailSender` protocol
(`ConsoleEmailSender` in dev; SMTP later, **no SES**). SSO + passkeys are later
slices that bolt onto `auth_identities`.

### Configuration — required vs safe defaults
`.env.example` is the single documented source of config. In `Settings`, only
**secrets/connection values** are required (no default): `DATABASE_URL`,
`JWT_SECRET`, `TURNSTILE_SECRET_KEY`. Everything else (URLs, TTLs, algorithm,
email backend) has a safe default in code and need not be set. Tests load
`.env.example` (via conftest) so they use the documented values. Alembic reads
only `DATABASE_URL` directly — migrations don't require the full app config.

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
# Opt-in DB integration tests (need a migrated DB; export DATABASE_URL at one):
CABBYCARDS_DB_TESTS=1 uv run pytest   # runs hermetic + all DB integration tests
uv run alembic revision --autogenerate -m "msg"  # new migration (datestamp rev id)
```

## Backlog

The canonical backlog lives in **Linear** (project *Cabby Cards*, issues `ALI-*`).
Highlights beyond the original roadmap: card **allocation model** (ALI-18 —
storage/deck are not siloed), **monetization** (ALI-6 iOS paywall + free codes),
**admin/referrals** (ALI-7), **import/export** (ALI-20). Current near-term order:

1. ✅ Scaffold + DB models + Scryfall cache (ALI-8)
2. 🚧 Auth (ALI-5) — **slice 1 email/password + Turnstile + verification + JWT built**; SSO + passkeys to follow
3. ⬜ Frontend scaffold (ALI-9) · Collection mgmt (ALI-11) · Deck building (ALI-12)
4. ⬜ Owned-only filter, wantlist export, cloud sync, iOS, …

## Git

Personal project — `alistairreynolds/cabbycards` (private) on GitHub. `gh` is
installed and authenticated (HTTPS). Feature branches per slice (e.g.
`ali-5-auth-foundation`); nothing is committed/pushed without asking.
