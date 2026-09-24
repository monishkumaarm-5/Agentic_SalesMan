import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.api.security import RateLimitMiddleware
from app.core.config import get_settings
from app.graph.builder import build_graph
from app.main import create_app
from app.services.chat import ChatService, build_response
from app.services.tracing import TraceStore
from tests.conftest import OVERVIEW, understanding


@pytest.fixture
def service(toolkit, tmp_path):
    settings = get_settings()
    return ChatService(build_graph(toolkit, settings, InMemorySaver()), settings, TraceStore(tmp_path / "t.sqlite"))


@pytest.fixture
def client(service, monkeypatch):
    monkeypatch.setattr("app.catalog.database.category_overview", lambda force=False: OVERVIEW)
    with TestClient(create_app(service=service, traces=service.traces)) as c:
        yield c


def test_chat_returns_a_full_response(client):
    body = client.post("/api/chat", json={"message": "phones under 30k"}).json()
    assert body["response_type"] == "recommendation"
    assert body["thread_id"]
    pick = body["recommendations"][0]["picks"][0]
    assert pick["name"] == "Redmi Note 14" and pick["specs"]
    assert body["suggestions"] == ["Compare the top two"]
    assert body["profile"]["categories"] == ["Mobile"]
    assert 0 < body["confidence"] <= 1


def test_chat_keeps_the_thread(client):
    first = client.post("/api/chat", json={"message": "phones", "thread_id": "abc-1"}).json()
    assert first["thread_id"] == "abc-1"
    history = client.get("/api/threads/abc-1/history").json()
    assert [t["role"] for t in history] == ["user", "assistant"]


def test_chat_validation(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "hi", "thread_id": "bad id!"}).status_code == 422


def test_stream_emits_status_then_final(client):
    with client.stream("POST", "/api/chat/stream", json={"message": "phones"}) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join(resp.iter_text())
    events = [
        (block.split("\n")[0][7:], json.loads(block.split("\n")[1][6:]))
        for block in raw.strip().split("\n\n") if block.startswith("event:")
    ]
    kinds = [k for k, _ in events]
    assert kinds[0] == "start" and kinds[-1] == "final"
    steps = [d["step"] for k, d in events if k == "status"]
    assert steps == ["understand", "retrieve", "recommend"]
    assert events[-1][1]["response_type"] == "recommendation"


def test_traces_record_decisions(client):
    client.post("/api/chat", json={"message": "phones", "thread_id": "tr-1"})
    [trace] = client.get("/api/traces", params={"thread_id": "tr-1"}).json()
    assert trace["action"] == "recommend"
    assert trace["candidates"]["Mobile"][0]["name"]
    assert [s["step"] for s in trace["steps"]] == ["understand", "retrieve", "recommend"]


def test_store_endpoints(client):
    assert client.get("/api/categories").json()[1]["name"] == "Mobile"
    company = client.get("/api/company").json()
    assert company["name"] == "Trein" and len(company["stores"]) == 3


def test_health_never_fails(client, monkeypatch):
    def down(*a, **k):
        raise RuntimeError("no db")
    monkeypatch.setattr("app.catalog.database.check_connectivity", down)
    body = client.get("/api/health").json()
    assert body["status"] == "degraded" and body["checks"]["database"] is False


def test_api_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "s3cret")
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    ok = client.post("/api/chat", json={"message": "hi"}, headers={"X-API-Key": "s3cret"})
    assert ok.status_code == 200
    assert client.get("/api/health").status_code == 200  # never needs a key


def test_errors_do_not_leak_details(client, service, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SELECT * FROM secret_table")
    monkeypatch.setattr(service, "ask", boom)
    resp = client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 500 and "secret" not in resp.text


def test_rate_limit_exempts_health():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=2)
    app.get("/api/health")(lambda: {"ok": True})
    app.get("/api/x")(lambda: {"ok": True})
    c = TestClient(app)
    assert [c.get("/api/x").status_code for _ in range(3)] == [200, 200, 429]
    assert all(c.get("/api/health").status_code == 200 for _ in range(5))


def test_build_response_handles_empty_state():
    body = build_response("t", {})
    assert body["answer"] == "" and body["recommendations"] == [] and body["confidence"] is None


def test_greeting_through_the_api(client, agents):
    agents.next_understanding = understanding(action="reply", reply="Hello!", categories=[])
    body = client.post("/api/chat", json={"message": "hi"}).json()
    assert body["answer"] == "Hello!" and body["response_type"] == "message"


def test_busy_thread_is_reported(service):
    lock = service._thread_lock("busy")
    lock.acquire()
    try:
        service.settings = service.settings.model_copy(update={"request_timeout_seconds": 1})
        events = list(service.stream("phones", "busy"))
    finally:
        lock.release()
    assert events[-1]["type"] == "error"
