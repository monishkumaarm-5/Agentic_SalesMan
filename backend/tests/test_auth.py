from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from APP import auth


def _make_app():
    app = FastAPI()

    @app.get("/api/secure", dependencies=[Depends(auth.require_api_key)])
    def secure():
        return {"ok": True}

    return app


def test_open_when_no_api_key_configured(monkeypatch):
    monkeypatch.setattr(auth.config, "API_KEY", "")
    client = TestClient(_make_app())
    assert client.get("/api/secure").status_code == 200


def test_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setattr(auth.config, "API_KEY", "secret123")
    client = TestClient(_make_app())
    assert client.get("/api/secure").status_code == 401


def test_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(auth.config, "API_KEY", "secret123")
    client = TestClient(_make_app())
    resp = client.get("/api/secure", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_accepts_correct_key(monkeypatch):
    monkeypatch.setattr(auth.config, "API_KEY", "secret123")
    client = TestClient(_make_app())
    resp = client.get("/api/secure", headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200
