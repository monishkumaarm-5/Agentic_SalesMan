"""
Lightweight execution tracing/observability: records, per chat turn, enough
of the pipeline's internal decisions to debug it after the fact --
routing, retrieval candidates + scores, evaluation scores, retries, and
latency -- without needing an external tracing backend.

Deliberately NOT threaded through LangGraph state: state has to stay
checkpoint-serializable (SqliteSaver pickles/JSONs it), and a trace record
assembled once at the end of `ask()` from the graph's final result is both
simpler and immune to LangGraph's per-node dict-merge semantics (see
Graph_State's docstring in ORCHE.py) silently dropping earlier nodes'
contributions.

Storage is a tiny SQLite table -- one row per turn, most recent first, JSON
payload -- good enough for local/portfolio use. A real production
deployment would ship this to OpenTelemetry/a real tracing backend instead;
see the README's Future Improvements.
"""
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

import config

logger = logging.getLogger("agentic_salesman.tracing")

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL
)
"""


def _db_path() -> str:
    return getattr(config, "TRACE_DB_PATH", "WORKFLOW/traces.sqlite")


@contextmanager
def _connection():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        conn.execute(_DDL)
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_trace(thread_id: str, payload: dict) -> None:
    """Never raises -- a tracing failure (disk full, permissions, whatever)
    should never take down the actual chat response."""
    try:
        with _connection() as conn:
            conn.execute(
                "INSERT INTO traces (thread_id, created_at, payload) VALUES (?, ?, ?)",
                (thread_id, time.time(), json.dumps(payload, default=str)),
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to persist trace for thread %s: %s", thread_id, exc)


def get_traces(thread_id: Optional[str] = None, limit: int = 20) -> list:
    """Most-recent-first list of trace payloads, optionally filtered to one
    thread_id."""
    try:
        with _connection() as conn:
            if thread_id:
                rows = conn.execute(
                    "SELECT payload FROM traces WHERE thread_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (thread_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload FROM traces ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [json.loads(row[0]) for row in rows]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to read traces: %s", exc)
        return []


class TraceBuilder:
    """Small accumulator used within a single `ask()` call -- not shared
    across requests, not put into graph state, just a plain object passed
    around the (non-graph) Python call stack of `_invoke()`."""

    def __init__(self, thread_id: str, question: str):
        self.thread_id = thread_id
        self.question = question
        self._start = time.monotonic()
        self.data = {"thread_id": thread_id, "question": question}

    def add(self, **fields) -> None:
        self.data.update(fields)

    def finish(self, **fields) -> dict:
        self.data.update(fields)
        self.data["latency_ms"] = round((time.monotonic() - self._start) * 1000, 1)
        record_trace(self.thread_id, self.data)
        return self.data
