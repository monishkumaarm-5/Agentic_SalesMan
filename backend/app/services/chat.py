"""
Runs chat turns through the workflow graph: blocking (`ask`) or as a
stream of progress events (`stream`), with a hard timeout and at most one
turn in flight per conversation thread.
"""
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.core.config import Settings
from app.models import ShoppingProfile
from app.services.tracing import TraceStore

logger = logging.getLogger("salesman.chat")

Emit = Callable[[dict], None]


class ChatTimeout(TimeoutError):
    pass


class ThreadBusy(RuntimeError):
    """Another message for the same conversation is still being answered."""


def build_response(thread_id: str, values: dict) -> dict:
    turn = values.get("turn") or {}
    recommendations = turn.get("recommendations") or []
    scores = [
        card.get("match", {}).get("overall")
        for group in recommendations for card in group.get("picks", [])
    ]
    scores = [s for s in scores if s is not None]
    try:
        profile = ShoppingProfile.model_validate(values.get("profile") or {})
    except Exception:  # noqa: BLE001
        profile = ShoppingProfile()
    return {
        "thread_id": thread_id,
        "answer": turn.get("answer") or "",
        "response_type": turn.get("response_type") or "message",
        "recommendations": recommendations,
        "products": turn.get("products") or [],
        "comparison": turn.get("comparison") or [],
        "suggestions": turn.get("suggestions") or [],
        "profile": profile.model_dump(exclude_none=True, exclude_defaults=True),
        "confidence": round(max(scores), 3) if scores else None,
    }


class ChatService:
    def __init__(self, graph, settings: Settings, traces: TraceStore | None = None):
        self.graph = graph
        self.settings = settings
        self.traces = traces
        self._executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="chat")
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ------------------------------------------------------------ internals
    def _thread_lock(self, thread_id: str) -> threading.Lock:
        with self._locks_guard:
            if len(self._locks) > 10_000:
                self._locks = {k: v for k, v in self._locks.items() if v.locked()}
            return self._locks.setdefault(thread_id, threading.Lock())

    def _run(self, message: str, thread_id: str, emit: Emit | None = None) -> dict:
        lock = self._thread_lock(thread_id)
        if not lock.acquire(timeout=self.settings.request_timeout_seconds):
            raise ThreadBusy("Still answering your previous message -- one moment.")
        started = time.monotonic()
        try:
            config = {"configurable": {"thread_id": thread_id}}
            for mode, chunk in self.graph.stream({"message": message}, config, stream_mode=["custom", "updates"]):
                if mode == "custom" and emit and isinstance(chunk, dict):
                    emit(chunk)
            values = self.graph.get_state(config).values
        finally:
            lock.release()

        response = build_response(thread_id, values)
        self._trace(thread_id, message, values, response, started)
        return response

    def _trace(self, thread_id, message, values, response, started) -> None:
        if not self.traces:
            return
        turn = values.get("turn") or {}
        self.traces.record(thread_id, {
            "thread_id": thread_id,
            "message": message,
            "action": turn.get("action"),
            "policy_override": turn.get("policy"),
            "degraded": turn.get("degraded"),
            "response_type": response["response_type"],
            "profile": response["profile"],
            "candidates": {
                cat: [{"name": r.get("name"), "score": (r.get("_scores") or {}).get("overall")} for r in rows]
                for cat, rows in (turn.get("candidates") or {}).items()
            },
            "notes": turn.get("notes"),
            "steps": turn.get("steps"),
            "latency_ms": round((time.monotonic() - started) * 1000),
        })

    # --------------------------------------------------------------- public
    def ask(self, message: str, thread_id: str) -> dict:
        future = self._executor.submit(self._run, message, thread_id)
        try:
            return future.result(timeout=self.settings.request_timeout_seconds)
        except FutureTimeout:
            raise ChatTimeout(f"No answer within {self.settings.request_timeout_seconds}s") from None

    def stream(self, message: str, thread_id: str) -> Iterator[dict]:
        """Yields {"type": "status", ...} events while the turn runs, then
        exactly one {"type": "final", "data": response} or
        {"type": "error", "message": ..., "code": ...}."""
        events: queue.Queue = queue.Queue()
        done = object()

        def work():
            try:
                events.put({"type": "final", "data": self._run(message, thread_id, events.put)})
            except ThreadBusy as exc:
                events.put({"type": "error", "code": "busy", "message": str(exc)})
            except Exception:  # noqa: BLE001
                logger.exception("Chat turn failed (thread %s)", thread_id)
                events.put({"type": "error", "code": "internal",
                            "message": "Sorry, something went wrong while answering. Please try again."})
            finally:
                events.put(done)

        self._executor.submit(work)
        deadline = time.monotonic() + self.settings.request_timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                yield {"type": "error", "code": "timeout",
                       "message": "That took too long to answer. Please try again."}
                return
            try:
                event = events.get(timeout=min(remaining, 15))
            except queue.Empty:
                yield {"type": "ping"}
                continue
            if event is done:
                return
            yield event

    def history(self, thread_id: str) -> list[dict]:
        values = self.graph.get_state({"configurable": {"thread_id": thread_id}}).values or {}
        return [m for m in values.get("messages", []) if m.get("content")]

    def profile(self, thread_id: str) -> dict:
        values = self.graph.get_state({"configurable": {"thread_id": thread_id}}).values or {}
        return build_response(thread_id, values)["profile"]
