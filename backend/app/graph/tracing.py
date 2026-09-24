"""
Readable, per-node logging of the workflow (enabled by LOG_GRAPH_STATE).

For every node it logs the state it received, the agent/tool it uses, the
update it returned and how long it took, plus each routing decision:

    ── turn 3f2a9c · thread 6b1e… ─────────────────────────────
    ▶ understand  [UnderstandingAgent · LLM]
        in : message='office use i need headphone' | profile={'categories': ['Headphone']} | ...
    ✓ understand  1840ms
        out: action=recommend | profile={'categories': ['Headphone'], 'use_cases': ['office']} | ...
    ↪ route understand → retrieve (action=recommend)
"""
import json
import logging
import time
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger("salesman.graph.trace")

NODE_AGENTS = {
    "guard": "InputGuard · rules: empty/too-long only",
    "understand": "UnderstandingAgent · LLM",
    "retrieve": "HybridSearch · semantic index + scoring, no LLM",
    "recommend": "RecommenderAgent · LLM",
    "advise": "AdvisorAgent · LLM + catalog lookup",
    "finalize": "Finalizer · no LLM",
}


def _short(value, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _compact_profile(profile: dict | None) -> dict:
    return {k: v for k, v in (profile or {}).items() if v not in (None, [], "")}


def summarize_state(state: dict) -> str:
    turn = state.get("turn") or {}
    shown = {cat: [c.get("name") for c in cards or []] for cat, cards in (state.get("shown") or {}).items()}
    parts = [
        f"message={_short(state.get('message', ''), 120)!r}",
        f"profile={_short(_compact_profile(state.get('profile')), 220)}",
        f"clarify_streak={state.get('clarify_streak') or 0}",
        f"history={len(state.get('messages') or [])} msgs",
    ]
    if shown:
        parts.append(f"shown={_short(shown, 220)}")
    if turn.get("action"):
        parts.append(f"turn.action={turn['action']}")
    if turn.get("candidates"):
        parts.append("turn.candidates=" + _short({c: len(r) for c, r in turn["candidates"].items()}))
    return " | ".join(parts)


def summarize_update(update: dict) -> str:
    if not update:
        return "(no changes)"
    parts = []
    turn = update.get("turn") or {}
    if "action" in turn:
        parts.append(f"action={turn['action']}")
    if turn.get("policy"):
        parts.append(f"policy_override={turn['policy']}")
    if turn.get("degraded"):
        parts.append("degraded=True (agent failed, used fallback)")
    if "profile" in update:
        parts.append(f"profile={_short(_compact_profile(update['profile']), 260)}")
    if "clarify_streak" in update:
        parts.append(f"clarify_streak={update['clarify_streak']}")
    if turn.get("candidates"):
        cands = {
            cat: [f"{r.get('name')} ({(r.get('_scores') or {}).get('overall', 0):.2f})" for r in rows]
            for cat, rows in turn["candidates"].items()
        }
        parts.append(f"candidates={_short(cands, 400)}")
    if turn.get("notes"):
        parts.append(f"notes={_short(turn['notes'])}")
    if turn.get("recommendations"):
        picks = {g["category"]: [c.get("name") for c in g.get("picks", [])] for g in turn["recommendations"]}
        parts.append(f"picks={_short(picks, 300)}")
    if turn.get("comparison"):
        parts.append(f"comparison={[c.get('name') for c in turn['comparison']]}")
    if turn.get("products"):
        parts.append(f"products={[c.get('name') for c in turn['products']]}")
    if turn.get("response_type"):
        parts.append(f"response_type={turn['response_type']}")
    if turn.get("answer"):
        parts.append(f"answer={_short(turn['answer'], 200)!r}")
    if turn.get("suggestions"):
        parts.append(f"suggestions={turn['suggestions']}")
    if "messages" in update:
        parts.append(f"+{len(update['messages'])} history msgs")
    return " | ".join(parts) or f"keys={sorted(update)}"


def _ids(config: RunnableConfig | None) -> tuple[str, str]:
    configurable = (config or {}).get("configurable", {}) or {}
    thread = str(configurable.get("thread_id", "?"))
    turn = str(configurable.get("turn_id") or (config or {}).get("run_id") or "")[:8]
    return thread, turn


def traced_node(name: str, fn: Callable[[dict], dict], enabled: bool) -> Callable:
    """Wraps a node function with enter/exit/error logging."""
    agent = NODE_AGENTS.get(name, name)

    def node(state: dict, config: RunnableConfig) -> dict:
        thread, turn = _ids(config)
        if enabled:
            if name == "guard":
                logger.info("── turn %s · thread %s %s", turn or "-", thread, "─" * 30)
            logger.info("▶ %-10s [%s]\n      in : %s", name, agent, summarize_state(state))
        started = time.monotonic()
        try:
            update = fn(state)
        except Exception:
            logger.exception("✗ %-10s failed after %dms (thread %s)", name,
                             (time.monotonic() - started) * 1000, thread)
            raise
        if enabled:
            logger.info("✓ %-10s %dms\n      out: %s", name, (time.monotonic() - started) * 1000,
                        summarize_update(update))
        return update

    node.__name__ = name
    return node


def traced_router(source: str, fn: Callable[[dict], str], enabled: bool) -> Callable:
    def route(state: dict) -> str:
        target = fn(state)
        if enabled:
            action = (state.get("turn") or {}).get("action")
            logger.info("↪ route %s → %s%s", source, target, f" (action={action})" if action else "")
        return target

    route.__name__ = f"route_after_{source}"
    return route
