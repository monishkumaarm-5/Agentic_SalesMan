"""Background index building and the per-node diagnostic logs."""
import logging

from app.graph import toolkit as tk_module
from app.models import ShoppingProfile
from app.retrieval.search import hybrid_search
from tests.conftest import PRODUCTS


def test_search_never_waits_for_the_index(monkeypatch):
    index = tk_module._BackgroundIndex()
    started = []
    monkeypatch.setattr(index, "_build", lambda: started.append(True))
    monkeypatch.setattr(tk_module, "_index", index)

    def semantic(query, category, k):
        return tk_module.get_index().search(query, category, k)

    rows = hybrid_search(semantic, "office headphone", ShoppingProfile(), "Mobile",
                         fallback=lambda c: [dict(p) for p in PRODUCTS if p["category"] == c])
    assert len(rows) == 3          # answered from the database instead
    assert index.status["state"] == "building"


def test_every_node_and_route_is_logged(run, agents, caplog):
    caplog.set_level(logging.INFO, logger="salesman")
    run("office headphones please")
    text = caplog.text
    for node in ("guard", "understand", "retrieve", "recommend", "finalize"):
        assert f"▶ {node}" in text and f"✓ {node}" in text
    assert "[UnderstandingAgent · LLM]" in text
    assert "↪ route understand → retrieve (action=recommend)" in text
    assert "candidates=" in text and "picks=" in text
    assert "message='office headphones please'" in text


def test_turn_summary_and_timeout_are_logged(service_factory, caplog):
    import time

    caplog.set_level(logging.INFO, logger="salesman")
    service, agents = service_factory()
    original = agents.understand

    def slow(variables):
        time.sleep(1.5)
        return original(variables)
    agents.understand = slow
    service.settings = service.settings.model_copy(update={"request_timeout_seconds": 1})
    events = list(service.stream("headphones", "slow-thread"))
    assert events[-1]["code"] == "timeout"
    assert "still in step 'understand'" in caplog.text
    time.sleep(1)  # let the background turn finish
    assert "END" in caplog.text and "response_type=recommendation" in caplog.text
