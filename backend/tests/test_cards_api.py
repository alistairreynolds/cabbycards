from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_requires_non_empty_query() -> None:
    # q has min_length=1, so an empty query is a 422 before any Scryfall call.
    client = TestClient(app)
    response = client.get("/cards/search", params={"q": ""})
    assert response.status_code == 422


def test_openapi_exposes_card_routes() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/cards/search" in paths
    assert "/cards/local-search" in paths
    assert "/cards/{scryfall_id}" in paths
