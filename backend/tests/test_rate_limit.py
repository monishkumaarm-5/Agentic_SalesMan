from fastapi import FastAPI
from starlette.testclient import TestClient

from APP.rate_limit import RateLimitMiddleware


def _make_app(limit):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=limit, window_seconds=60)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/other")
    def other():
        return {"ok": True}

    return app


def test_allows_requests_under_the_limit():
    client = TestClient(_make_app(3))
    for _ in range(3):
        assert client.get("/api/ping").status_code == 200


def test_blocks_requests_over_the_limit():
    client = TestClient(_make_app(2))
    client.get("/api/ping")
    client.get("/api/ping")
    resp = client.get("/api/ping")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_only_applies_to_api_paths():
    client = TestClient(_make_app(1))
    client.get("/api/ping")
    assert client.get("/api/ping").status_code == 429
    assert client.get("/other").status_code == 200


def test_limit_of_zero_disables_the_middleware():
    client = TestClient(_make_app(0))
    for _ in range(5):
        assert client.get("/api/ping").status_code == 200
