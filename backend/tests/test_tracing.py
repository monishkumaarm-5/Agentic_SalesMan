"""Tests for WORKFLOW/tracing.py's SQLite-backed execution trace log."""
import json

from WORKFLOW import tracing


def test_record_and_get_traces_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))
    tracing.record_trace("thread-1", {"question": "hi", "latency_ms": 12})
    traces = tracing.get_traces()
    assert len(traces) == 1
    assert traces[0]["question"] == "hi"


def test_get_traces_filters_by_thread_id(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))
    tracing.record_trace("thread-a", {"question": "from a"})
    tracing.record_trace("thread-b", {"question": "from b"})

    only_a = tracing.get_traces(thread_id="thread-a")
    assert len(only_a) == 1
    assert only_a[0]["question"] == "from a"


def test_get_traces_returns_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))
    tracing.record_trace("thread-1", {"question": "first"})
    tracing.record_trace("thread-1", {"question": "second"})

    traces = tracing.get_traces(thread_id="thread-1")
    assert [t["question"] for t in traces] == ["second", "first"]


def test_get_traces_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))
    for i in range(5):
        tracing.record_trace("thread-1", {"question": str(i)})

    assert len(tracing.get_traces(thread_id="thread-1", limit=2)) == 2


def test_record_trace_never_raises_on_bad_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))

    class Unserializable:
        pass

    # json.dumps(..., default=str) should stringify it rather than raising
    tracing.record_trace("thread-1", {"weird": Unserializable()})
    traces = tracing.get_traces(thread_id="thread-1")
    assert len(traces) == 1


def test_trace_builder_finish_persists_and_measures_latency(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path / "traces.sqlite"))
    builder = tracing.TraceBuilder("thread-1", "recommend a phone")
    builder.add(context="MOBILE")
    data = builder.finish(answer="here you go")

    assert data["question"] == "recommend a phone"
    assert data["context"] == "MOBILE"
    assert data["answer"] == "here you go"
    assert data["latency_ms"] >= 0

    stored = tracing.get_traces(thread_id="thread-1")
    assert stored[0]["answer"] == "here you go"


def test_get_traces_returns_empty_list_when_store_is_unreadable(tmp_path, monkeypatch):
    # Point at a directory instead of a file -- sqlite3.connect will fail.
    monkeypatch.setattr(tracing.config, "TRACE_DB_PATH", str(tmp_path))
    assert tracing.get_traces() == []
