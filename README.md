# CabbyCards

MTG (Magic: The Gathering) collection and deck management, with a companion iOS
app for card scanning. Commander is the primary use case.

Monorepo:

- `backend/` — Python + FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- `frontend/` — Vue 3 + Vite + Pinia SPA *(later slice)*
- `ios/` — Capacitor shell + native Swift Vision scanner *(later slice)*

See [`CLAUDE.md`](./CLAUDE.md) for architecture decisions and conventions.

## Backend quick start

```bash
docker compose up -d db                 # Postgres on host port 5433
cd backend
cp .env.example .env                    # then edit SCRYFALL_USER_AGENT
uv sync                                 # install deps into .venv
uv run alembic upgrade head             # create the schema (enables pg_trgm)
uv run uvicorn app.main:app --reload    # http://127.0.0.1:8000/docs
```

Tests:

```bash
cd backend
uv run pytest                                   # hermetic unit/API tests
uv run ruff check .
CABBYCARDS_DB_TESTS=1 uv run pytest tests/test_integration_db.py  # needs a migrated DB
```
