"""Per-turn decision log in SQLite -- what the agent decided, why, and
how long each step took. Never raises."""
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger("salesman.tracing")

_DDL = """CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL
)"""


class TraceStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.execute(_DDL)
        return conn

    def record(self, thread_id: str, payload: dict) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute("INSERT INTO traces (thread_id, created_at, payload) VALUES (?, ?, ?)",
                             (thread_id, time.time(), json.dumps(payload, default=str)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not record trace: %s", exc)

    def list(self, thread_id: str | None = None, limit: int = 20) -> list:
        try:
            with self._lock, self._connect() as conn:
                if thread_id:
                    rows = conn.execute("SELECT payload FROM traces WHERE thread_id = ? ORDER BY id DESC LIMIT ?",
                                        (thread_id, limit)).fetchall()
                else:
                    rows = conn.execute("SELECT payload FROM traces ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [json.loads(r[0]) for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read traces: %s", exc)
            return []
