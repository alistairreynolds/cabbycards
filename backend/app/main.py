from fastapi import FastAPI

from app.api.routes import auth, cards, collection

app = FastAPI(title="CabbyCards API", version="0.1.0")
app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(collection.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — no dependencies, safe for load balancers to poll.

    See: tests/test_cards_api.py
    """
    return {"status": "ok"}
