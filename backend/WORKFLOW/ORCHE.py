import itertools
import json
import logging
import operator
import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Annotated, Optional, TypedDict

import config

# The AGENTS modules below instantiate their Gemini clients as soon as they
# are imported, which means GOOGLE_API_KEY has to already be in the
# environment *before* those imports run. `import config` above only reads
# config.py -- it does not touch os.environ -- so the assignment below must
# stay ahead of every `from AGENTS...` import in this file.
if getattr(config, "GOOGLE_API_KEY", None):
    os.environ.setdefault("GOOGLE_API_KEY", config.GOOGLE_API_KEY)

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from AGENTS.ENTRYSAFEGAURD_AGENT import isvalidquery as entry_guard_check
from AGENTS.EXIT_SAFE_GAURD_AGENT import evaluate_response
from AGENTS.HEADPHONE_SALES_AGENT import HEADPHONE_SALES_AGENT
from AGENTS.LAPTOP_SALES_AGENT import LAPTOP_SALES_AGENT
from AGENTS.MOBILE_SALES_AGENT import MOBILE_SALES_AGENT
from AGENTS.REQUIREMENT_EXTRACTOR_AGENT import extract_requirements
from DATABASE.SQL_CONNECTOR import DB_CONNECTOR
from WORKFLOW.retrieval import format_candidates_for_prompt, hybrid_search
from WORKFLOW.tracing import TraceBuilder

logger = logging.getLogger("agentic_salesman.orche")

DECLINE_MESSAGE = (
    "Sorry, I can only answer questions related to phones, laptops and headphones."
)
GREETING_MESSAGE = (
    "Hi there! I'm your Agentic SalesMan assistant. Ask me about **phones**, "
    "**laptops** or **headphones** and I'll help you find the right one."
)
MAX_HISTORY_TURNS = 6  # ~3 exchanges of context handed to the sales agents

CATEGORY_LABELS = {
    "MOBILE": "Phone",
    "LAPTOP": "Laptop",
    "HEADPHONE": "Headphone",
}


class Graph_State(TypedDict):
    question: str
    answer: str
    context: str
    categories: list
    product: Optional[dict]
    # Retrieval candidates (category -> scored product list, see
    # WORKFLOW/retrieval.py) and the requirements they were scored against
    # -- per-turn scratch, surfaced in the API response and the execution
    # trace, and re-read by the evaluator/retry step in exit_gaurd_agent.
    candidates: Optional[dict]
    requirements: Optional[dict]
    evaluation: Optional[dict]
    retries: int
    # The only field that should genuinely persist and grow across turns of
    # the same thread_id -- every other field reflects just the latest turn,
    # so it's plain last-write-wins (LangGraph's default) rather than a
    # reducer. (A reducer here would also *accumulate* across every past
    # invoke() call via the checkpointer, not just within one turn's work --
    # fine for history, wrong for anything meant to be per-turn scratch
    # space, which is why category fan-out is handled inside a single node
    # below instead of as separate reducer-merged graph branches.)
    history: Annotated[list, operator.add]


# ---------------------------------------------------------------------------
# Vector store + compiled graph + checkpointer are all expensive/stateful to
# build, so they're created lazily on first use and cached, rather than at
# import time. That lets the FastAPI app import this module -- and even boot
# and serve /api/health -- before config.py / the database are fully set up.
# ---------------------------------------------------------------------------
_vector_store: Optional[DB_CONNECTOR] = None
_graph = None
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent-pipeline")

AGENT_FUNCS = {
    "MOBILE": (MOBILE_SALES_AGENT, lambda: get_vector_store().phone_vector_database()),
    "LAPTOP": (LAPTOP_SALES_AGENT, lambda: get_vector_store().laptop_vector_database()),
    "HEADPHONE": (HEADPHONE_SALES_AGENT, lambda: get_vector_store().headphone_vector_database()),
}


def get_vector_store() -> DB_CONNECTOR:
    global _vector_store
    if _vector_store is None:
        _vector_store = DB_CONNECTOR()
    return _vector_store


def _build_checkpointer() -> SqliteSaver:
    path = getattr(config, "CHECKPOINT_DB_PATH", "WORKFLOW/checkpoints.sqlite")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _recent_history_text(history: list) -> str:
    if not history:
        return ""
    recent = history[-MAX_HISTORY_TURNS:]
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


def _build_user_request(state: Graph_State) -> str:
    """Give the sales agents the recent conversation, not just the latest
    message, so a follow-up like "under $1000" after "recommend a laptop"
    actually has something to anchor to."""
    history_text = _recent_history_text(state.get("history", []))
    question = state["question"]
    if not history_text:
        return question
    return (
        f"Conversation so far (most recent last):\n{history_text}\n\n"
        f"Customer's current message: {question}"
    )


def _extract_product_json(raw_text: Optional[str]) -> Optional[dict]:
    """Best-effort parse of the product agent's raw output as JSON (it's
    asked to return JSON in the prompt, but nothing enforces it structurally,
    so this must never raise -- a bad parse just means no product card)."""
    if not raw_text:
        return None
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _flatten_candidates(candidates_by_category: Optional[dict]) -> list:
    if not candidates_by_category:
        return []
    return list(itertools.chain.from_iterable(candidates_by_category.values()))


def _compose_results(results: list) -> tuple:
    """Merges one or more per-category `_run_one_category` results into the
    final (answer, product, candidates_by_category) triple. Shared between
    the first pass (sales_agents) and an evaluator-triggered retry
    (exit_gaurd_agent) so both compose identically."""
    if len(results) == 1:
        r = results[0]
        return r["text"], r["product"], {r["category"]: r["candidates"]}

    sections = []
    products = {}
    candidates_by_category = {}
    for r in results:
        label = CATEGORY_LABELS.get(r["category"], r["category"].title())
        sections.append(f"## {label}\n\n{r['text']}")
        if r["product"]:
            products[r["category"]] = r["product"]
        candidates_by_category[r["category"]] = r["candidates"]
    return "\n\n---\n\n".join(sections), (products or None), candidates_by_category


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
def entry_gaurd_agent(state: Graph_State):
    question = state["question"]
    history_update = {"history": [{"role": "user", "content": question}]}
    valid = entry_guard_check(question)

    if not valid["query"]:
        logger.info("Entry Guard : Query Rejected")
        return {"context": "DENY", "categories": [], **history_update}

    logger.info("Entry Guard : Query Accepted")
    categories = []
    if valid.get("mobile"):
        categories.append("MOBILE")
    if valid.get("laptop"):
        categories.append("LAPTOP")
    if valid.get("headphone"):
        categories.append("HEADPHONE")

    if not categories and valid.get("greeting"):
        return {"context": "GREETING", "categories": [], **history_update}

    if not categories:
        # Judged "relevant" but didn't match a product category or a
        # greeting -- decline instead of crashing the router.
        return {"context": "DENY", "categories": [], **history_update}

    return {"context": "+".join(categories), "categories": categories, **history_update}


def router(state: Graph_State):
    context = state.get("context")
    if context == "DENY":
        return "chatbot"
    if context == "GREETING":
        return "greeting"
    return "sales_agents"


def chatbot(state: Graph_State):
    # Return only the fields this node actually changes. Returning the
    # whole (mutated-in-place) state dict would also re-write "history" --
    # unchanged -- and since history uses an additive reducer, re-writing
    # the same value duplicates it instead of being a harmless no-op.
    return {"answer": DECLINE_MESSAGE, "product": None, "candidates": None}


def greeting(state: Graph_State):
    return {"answer": GREETING_MESSAGE, "product": None, "candidates": None}


def _run_one_category(
    state: Graph_State,
    category_key: str,
    agent_fn,
    vector_getter,
    requirements: dict,
    retry_feedback: Optional[str] = None,
) -> dict:
    query = state["question"]
    user_request = _build_user_request(state)
    if retry_feedback:
        user_request += (
            f"\n\nYour previous answer was rejected by quality review for: "
            f"{retry_feedback}. Regenerate, staying strictly grounded in the "
            f"RAG data below and fixing these issues."
        )

    db = vector_getter()
    candidates = hybrid_search(db, query, requirements, top_k=5)
    rag_data = format_candidates_for_prompt(candidates)

    result = agent_fn(user_request, rag_data)
    text = getattr(result, "raw", None) or str(result)

    product = None
    tasks_output = getattr(result, "tasks_output", None)
    if tasks_output:
        product = _extract_product_json(getattr(tasks_output[0], "raw", None))

    usage = getattr(result, "token_usage", None)
    if usage:
        logger.info("%s crew token usage: %s", category_key, usage)

    return {"category": category_key, "text": text, "product": product, "candidates": candidates}


def sales_agents(state: Graph_State):
    """Runs every matched category's crew (sequentially -- CrewAI/litellm
    calls aren't guaranteed thread-safe, so this trades a bit of latency on
    multi-category questions for reliability) and merges the results. A
    single-category question -- the common case -- behaves exactly as
    before, just now backed by hybrid (SQL+vector, scored) retrieval instead
    of plain top-k semantic search."""
    categories = [c for c in state.get("categories", []) if c in AGENT_FUNCS]
    if not categories:
        return {"answer": DECLINE_MESSAGE, "context": "DENY", "product": None, "candidates": None}

    requirements = extract_requirements(
        state["question"], _recent_history_text(state.get("history", []))
    )
    results = [
        _run_one_category(state, category, *AGENT_FUNCS[category], requirements)
        for category in categories
    ]
    answer, product, candidates = _compose_results(results)
    return {"answer": answer, "product": product, "candidates": candidates, "requirements": requirements}


def exit_gaurd_agent(state: Graph_State):
    """Final step for every path. For DENY/GREETING (canned replies, never
    LLM-generated from arbitrary RAG data) this just records history. For a
    real sales-agent answer, it runs the scored evaluator
    (AGENTS/EXIT_SAFE_GAURD_AGENT.py); a failing score triggers one retry of
    the sales crew(s) with the evaluator's own feedback appended, and only
    falls back to the standard decline message if the retry also fails."""
    answer = state.get("answer", DECLINE_MESSAGE)
    update = {}
    context = state.get("context")

    if context in ("DENY", "GREETING"):
        update["evaluation"] = None
        update["retries"] = 0
    else:
        requirements = state.get("requirements") or {}
        candidates = state.get("candidates")
        evaluation = evaluate_response(
            state["question"],
            answer,
            _flatten_candidates(candidates),
            requirements,
            min_score=getattr(config, "EVALUATION_MIN_SCORE", 0.6),
        )
        retries = 0

        if not evaluation["passed"]:
            if getattr(config, "ENABLE_EVALUATOR_RETRY", True):
                logger.warning(
                    "Exit Evaluator : score %.2f below threshold, retrying (%s)",
                    evaluation.get("overall") or 0.0,
                    evaluation.get("reasons"),
                )
                retries = 1
                feedback = "; ".join(evaluation.get("reasons") or []) or (
                    "the response did not meet the quality bar"
                )
                categories = [c for c in state.get("categories", []) if c in AGENT_FUNCS]
                retry_results = [
                    _run_one_category(
                        state, category, *AGENT_FUNCS[category], requirements, retry_feedback=feedback
                    )
                    for category in categories
                ]
                new_answer, new_product, new_candidates = _compose_results(retry_results)
                re_evaluation = evaluate_response(
                    state["question"],
                    new_answer,
                    _flatten_candidates(new_candidates),
                    requirements,
                    min_score=getattr(config, "EVALUATION_MIN_SCORE", 0.6),
                )
                if re_evaluation["passed"]:
                    answer = new_answer
                    update["product"] = new_product
                    update["candidates"] = new_candidates
                    evaluation = re_evaluation
                else:
                    logger.warning("Exit Evaluator : retry also failed, declining")
                    answer = DECLINE_MESSAGE
                    update["context"] = "DENY"
                    update["product"] = None
                    update["candidates"] = None
                    evaluation = re_evaluation
            else:
                logger.warning(
                    "Exit Evaluator : score %.2f below threshold, retry disabled, declining",
                    evaluation.get("overall") or 0.0,
                )
                answer = DECLINE_MESSAGE
                update["context"] = "DENY"
                update["product"] = None
                update["candidates"] = None
        else:
            logger.info("Exit Evaluator : Answer Accepted (score %.2f)", evaluation.get("overall") or 0.0)

        update["evaluation"] = evaluation
        update["retries"] = retries

    update["answer"] = answer
    update["history"] = [{"role": "assistant", "content": answer}]
    return update


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------
def get_graph():
    global _graph
    if _graph is not None:
        return _graph

    builder = StateGraph(Graph_State)
    builder.add_node("entry_guard_agent", entry_gaurd_agent)
    builder.add_node("chatbot", chatbot)
    builder.add_node("greeting", greeting)
    builder.add_node("sales_agents", sales_agents)
    builder.add_node("exit_guard_agent", exit_gaurd_agent)

    builder.add_edge(START, "entry_guard_agent")
    builder.add_conditional_edges("entry_guard_agent", router)
    builder.add_edge("chatbot", "exit_guard_agent")
    builder.add_edge("greeting", "exit_guard_agent")
    builder.add_edge("sales_agents", "exit_guard_agent")
    builder.add_edge("exit_guard_agent", END)

    _graph = builder.compile(checkpointer=_build_checkpointer())
    return _graph


def _confidence_from(evaluation: Optional[dict], candidates: Optional[dict]) -> Optional[float]:
    if evaluation and evaluation.get("overall") is not None:
        return evaluation["overall"]
    flat = _flatten_candidates(candidates)
    if flat:
        best = max(flat, key=lambda c: c.get("_scores", {}).get("overall", 0.0))
        return best.get("_scores", {}).get("overall")
    return None


def _invoke(question: str, thread_id: str) -> dict:
    tracer = TraceBuilder(thread_id, question)
    graph = get_graph()
    result = graph.invoke(
        {"question": question},
        config={"configurable": {"thread_id": thread_id}},
    )

    candidates = result.get("candidates")
    evaluation = result.get("evaluation")
    tracer.add(
        context=result.get("context"),
        categories=result.get("categories"),
        requirements=result.get("requirements"),
        candidates=candidates,
        evaluation=evaluation,
        retries=result.get("retries", 0),
    )
    tracer.finish()

    return {
        "answer": result.get("answer", DECLINE_MESSAGE),
        "context": result.get("context", "DENY"),
        "product": result.get("product"),
        "candidates": candidates,
        "confidence": _confidence_from(evaluation, candidates),
    }


def ask(question: str, thread_id: str = "default") -> dict:
    """Single entry point the FastAPI layer (and anything else) calls.
    Runs the pipeline in a worker thread with a hard timeout, so a stuck
    LLM/DB call can't hang the request forever."""
    timeout = getattr(config, "REQUEST_TIMEOUT_SECONDS", 90)
    future = _executor.submit(_invoke, question, thread_id)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        raise TimeoutError(f"Agent pipeline timed out after {timeout}s") from None


def get_history(thread_id: str) -> list:
    """Read back the accumulated conversation for a thread from the
    checkpointer, without running the pipeline."""
    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    if not snapshot or not snapshot.values:
        return []
    return snapshot.values.get("history", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    response = ask("I want high quality headphones please give me")
    print(response["answer"])
