"""
Runs chat turns through the workflow graph: blocking (`ask`) or as a
stream of progress events (`stream`), with a hard timeout and at most one
turn in flight per conversation thread.
"""
import logging
import queue
import threading
import time
import uuid
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
        # thread_id -> {"turn", "step", "since"}: what each running turn is doing,
        # so a timeout can say where it got stuck.
        self._active: dict[str, dict] = {}

    # ------------------------------------------------------------ internals
    def _thread_lock(self, thread_id: str) -> threading.Lock:
        with self._locks_guard:
            if len(self._locks) > 10_000:
                self._locks = {k: v for k, v in self._locks.items() if v.locked()}
            return self._locks.setdefault(thread_id, threading.Lock())

    def _run(self, message: str, thread_id: str, emit: Emit | None = None) -> dict:
        turn_id = uuid.uuid4().hex[:8]
        lock = self._thread_lock(thread_id)
        if not lock.acquire(blocking=False):
            active = self._active.get(thread_id, {})
            logger.info("Turn %s (thread %s) waiting: turn %s still running step '%s'",
                        turn_id, thread_id, active.get("turn"), active.get("step"))
            if not lock.acquire(timeout=self.settings.request_timeout_seconds):
                raise ThreadBusy("Still answering your previous message -- one moment.")
        started = time.monotonic()
        self._active[thread_id] = {"turn": turn_id, "step": "guard", "since": started}
        logger.info("Turn %s START thread=%s message=%r", turn_id, thread_id, message[:200])
        try:
            config = {"configurable": {"thread_id": thread_id, "turn_id": turn_id}}
            for mode, chunk in self.graph.stream({"message": message}, config, stream_mode=["custom", "updates"]):
                if mode == "custom" and isinstance(chunk, dict):
                    if chunk.get("step"):
                        self._active[thread_id] = {"turn": turn_id, "step": chunk["step"], "since": time.monotonic()}
                    if emit:
                        emit(chunk)
                elif mode == "updates" and isinstance(chunk, dict):
                    for node in chunk:
                        self._active[thread_id] = {"turn": turn_id, "step": f"after {node}", "since": time.monotonic()}
            values = self.graph.get_state(config).values
        except Exception:
            logger.exception("Turn %s FAILED after %dms in step '%s'", turn_id,
                             (time.monotonic() - started) * 1000, self._active.get(thread_id, {}).get("step"))
            raise
        finally:
            self._active.pop(thread_id, None)
            lock.release()

        response = build_response(thread_id, values)
        turn = values.get("turn") or {}
        logger.info(
            "Turn %s END %dms | action=%s | response_type=%s | steps=%s | picks=%s | profile=%s",
            turn_id, (time.monotonic() - started) * 1000, turn.get("action"), response["response_type"],
            ", ".join(f"{s['step']}:{s['ms']}ms" for s in turn.get("steps") or []) or "-",
            [c.get("name") for g in response["recommendations"] for c in g.get("picks", [])] or "-",
            response["profile"] or "{}",
        )
        self._trace(thread_id, message, values, response, started)
        return response

    def _log_timeout(self, thread_id: str) -> None:
        active = self._active.get(thread_id)
        if active:
            logger.warning(
                "Turn %s (thread %s) exceeded %ss -- still in step '%s' for %.1fs. It keeps running in the "
                "background and the next message for this thread waits for it.",
                active["turn"], thread_id, self.settings.request_timeout_seconds, active["step"],
                time.monotonic() - active["since"])
        else:
            logger.warning("Thread %s exceeded %ss", thread_id, self.settings.request_timeout_seconds)

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
            self._log_timeout(thread_id)
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
                self._log_timeout(thread_id)
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
