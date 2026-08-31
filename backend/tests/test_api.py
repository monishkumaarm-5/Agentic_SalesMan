from unittest.mock import patch

from fastapi.testclient import TestClient

from APP.main import app

client = TestClient(app)


def test_health_reports_ok_when_everything_configured(monkeypatch):
    monkeypatch.setattr("ENDPOINTS.endpoints.config.GOOGLE_API_KEY", "real-key")
    monkeypatch.setattr("ENDPOINTS.endpoints.config.DB_PASSWORD", "real-password")
    with patch("ENDPOINTS.endpoints.check_mysql_connectivity", return_value=None):
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["database_reachable"] is True


def test_health_reports_degraded_and_never_raises(monkeypatch):
    monkeypatch.setattr("ENDPOINTS.endpoints.config.GOOGLE_API_KEY", "your-google-api-key-here")
    with patch("ENDPOINTS.endpoints.check_mysql_connectivity", side_effect=RuntimeError("no db")):
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database_reachable"] is False
    assert "database_error" in body["checks"]


def test_health_does_not_require_an_api_key(monkeypatch):
    monkeypatch.setattr("APP.auth.config.API_KEY", "secret")
    with patch("ENDPOINTS.endpoints.check_mysql_connectivity", return_value=None):
        resp = client.get("/api/health")
    assert resp.status_code == 200


def test_chat_returns_the_agent_response():
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={"answer": "hi", "context": "MOBILE", "product": None},
    ):
        resp = client.post("/api/chat", json={"question": "recommend a phone"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "hi"
    assert body["context"] == "MOBILE"
    assert "thread_id" in body


def test_chat_reuses_the_given_thread_id():
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={"answer": "hi", "context": "MOBILE", "product": None},
    ) as mock_ask:
        resp = client.post("/api/chat", json={"question": "recommend a phone", "thread_id": "abc"})
    assert resp.json()["thread_id"] == "abc"
    mock_ask.assert_called_once_with("recommend a phone", thread_id="abc")


def test_chat_surfaces_product_data():
    product = {"recommended_product": "iPhone 14", "reason": "great value"}
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={"answer": "hi", "context": "MOBILE", "product": product},
    ):
        resp = client.post("/api/chat", json={"question": "recommend a phone"})
    assert resp.json()["product"] == product


def test_chat_times_out_as_504():
    with patch("ENDPOINTS.endpoints.ask", side_effect=TimeoutError("too slow")):
        resp = client.post("/api/chat", json={"question": "recommend a phone"})
    assert resp.status_code == 504


def test_chat_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setattr("APP.auth.config.API_KEY", "secret123")
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={"answer": "hi", "context": "MOBILE", "product": None},
    ):
        resp = client.post("/api/chat", json={"question": "hi"})
    assert resp.status_code == 401


def test_chat_accepts_the_correct_api_key(monkeypatch):
    monkeypatch.setattr("APP.auth.config.API_KEY", "secret123")
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={"answer": "hi", "context": "MOBILE", "product": None},
    ):
        resp = client.post(
            "/api/chat", json={"question": "hi"}, headers={"X-API-Key": "secret123"}
        )
    assert resp.status_code == 200


def test_history_endpoint_returns_turns():
    with patch("ENDPOINTS.endpoints.get_history", return_value=[{"role": "user", "content": "hi"}]):
        resp = client.get("/api/history/abc")
    assert resp.status_code == 200
    assert resp.json() == [{"role": "user", "content": "hi"}]


def test_chat_surfaces_candidates_and_confidence():
    candidates = {"MOBILE": [{"name": "Pixel 9", "_scores": {"overall": 0.9}}]}
    with patch(
        "ENDPOINTS.endpoints.ask",
        return_value={
            "answer": "hi",
            "context": "MOBILE",
            "product": None,
            "candidates": candidates,
            "confidence": 0.9,
        },
    ):
        resp = client.post("/api/chat", json={"question": "recommend a phone"})
    body = resp.json()
    assert body["candidates"] == candidates
    assert body["confidence"] == 0.9


def test_compare_returns_the_comparison():
    comparison = {
        "category": "laptop",
        "products": {"A": {"price": 1}, "B": {"price": 2}},
        "differing_fields": ["price"],
        "missing": [],
    }
    with patch("ENDPOINTS.endpoints.compare_products", return_value=comparison):
        resp = client.post(
            "/api/compare", json={"category": "laptop", "product_names": ["A", "B"]}
        )
    assert resp.status_code == 200
    assert resp.json() == comparison


def test_compare_rejects_a_single_product_name():
    resp = client.post("/api/compare", json={"category": "laptop", "product_names": ["A"]})
    assert resp.status_code == 422  # Pydantic min_length violation


def test_compare_returns_400_when_products_are_not_found():
    from TOOLS.product_tools import ProductToolError

    with patch(
        "ENDPOINTS.endpoints.compare_products",
        side_effect=ProductToolError("could only find 1 of 2 products"),
    ):
        resp = client.post(
            "/api/compare", json={"category": "laptop", "product_names": ["A", "B"]}
        )
    assert resp.status_code == 400


def test_compare_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setattr("APP.auth.config.API_KEY", "secret123")
    resp = client.post("/api/compare", json={"category": "laptop", "product_names": ["A", "B"]})
    assert resp.status_code == 401


def test_traces_endpoint_returns_the_log():
    fake_traces = [{"thread_id": "abc", "question": "hi", "latency_ms": 12.3}]
    with patch("ENDPOINTS.endpoints.get_traces", return_value=fake_traces) as mock_get:
        resp = client.get("/api/traces?thread_id=abc&limit=5")
    assert resp.status_code == 200
    assert resp.json() == fake_traces
    mock_get.assert_called_once_with(thread_id="abc", limit=5)


def test_traces_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setattr("APP.auth.config.API_KEY", "secret123")
    resp = client.get("/api/traces")
    assert resp.status_code == 401
