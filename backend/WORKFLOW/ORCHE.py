"""
LangGraph pipeline for the shopping assistant.

Restructured architecture (see the "SalesMan Redesign" write-up for the
diagram this implements):

  guardrail_in (predefined rules, no LLM)
      -> business_need   (LLM: category + budget/use-case/brand + psychology)
      -> product_expert  (LLM: RAG-grounded recommendation)
      -> sales_consultant(LLM: storytelling + comparison, or a follow-up
                           answer / redirect once a pitch has been shown)
      -> guardrail_out (predefined rules, no LLM)

CrewAI is gone -- what used to be four chained CrewAI agents per category
is now two plain LangGraph nodes (business_need, product_expert) plus a
third (sales_consultant) doing what the old Storytelling/Sales Consultant
crew tasks did, each a single structured Gemini call grounded in the same
RAG data the old crew was grounded in. The old LLM-backed entry guard and
5-dimension exit evaluator are both replaced by AGENTS/GUARDRAIL_AGENT.py,
a predefined-rules filter run on the way in and the way out -- no LLM
spent on a message that was always going to be rejected, or on grading an
answer whose only real grounding check (does it actually contain a real
product name?) doesn't need an LLM either.

Every LLM-backed node returns its own routing decision (`next`) instead
of reading a shared router() -- see the four node functions below. A
"go back to an earlier agent" redirect (Sales Consultant deciding the
customer actually wants a different product or category) is applied to
persistent state (clearing `pitch_delivered` / `business_need[cat]
["satisfied"]`) rather than a same-turn graph loop: the customer's next
message is what guardrail_in reads to resume at the right agent. Forward
hand-offs (business_need -> product_expert -> sales_consultant), by
contrast, ARE real same-turn graph edges, so a customer who already gave
enough detail still gets a full recommendation in one turn, same as
before.

"Human in the loop" is the ordinary chat turn: an agent that needs more
from the customer sets `answer` to its question and ends the turn (routes
to guardrail_out -> END) instead of guessing -- the customer's reply,
whenever it arrives, is what resumes the conversation. This keeps the
existing request/response HTTP contract intact (no change needed to
ENDPOINTS/endpoints.py or the frontend) while still giving every agent a
real pause-and-ask point.

Every node appends one entry to `logs` -- {agent, ts, next, ...} -- so the
whole turn's decision path is inspectable afterward (also folded into the
existing WORKFLOW/tracing.py trace record).
"""
import logging
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Annotated, Optional, TypedDict

import config

if getattr(config, "GOOGLE_API_KEY", None):
    os.environ.setdefault("GOOGLE_API_KEY", config.GOOGLE_API_KEY)

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from AGENTS.GUARDRAIL_AGENT import entry_check, exit_check, detect_categories
from AGENTS.BUSINESS_NEED_AGENT import assess as business_need_assess, MIN_CONSULTATION_ROUNDS
from AGENTS.PRODUCT_EXPERT_AGENT import recommend as product_expert_recommend
from AGENTS.SALES_CONSULTANT_AGENT import consult as sales_consultant_consult

from DATABASE.SQL_CONNECTOR import DB_CONNECTOR, list_categories
from WORKFLOW.recommendations import build_top_picks
from WORKFLOW.retrieval import format_candidates_for_prompt, hybrid_search
from WORKFLOW.tracing import TraceBuilder


logger = logging.getLogger("agentic_salesman.orche")

COMPANY_NAME = getattr(config, "COMPANY_NAME", "Trein")

def _store_cities() -> list:
    """Distinct city names from config.STORE_LOCATIONS -- for the
    Business Need Agent to know which cities to offer."""
    stores = getattr(config, "STORE_LOCATIONS", None) or []
    cities = list(dict.fromkeys(
        str(s.get("city", "")).strip()
        for s in stores
        if s.get("city") and str(s.get("city")).strip()
    ))
    return cities

DECLINE_MESSAGE = (
    f"Sorry, I can only help with questions about the products {COMPANY_NAME} sells."
)

GREETING_MESSAGE = (
    f"Hi there! I'm the {COMPANY_NAME} shopping assistant. Ask me about "
    f"anything we sell -- mobiles, laptops, TVs, appliances and more -- "
    f"and I'll help you find the right one."
)

MAX_HISTORY_TURNS = 6

# Safety valve on same-turn forward chaining (business_need ->
# product_expert -> sales_consultant is at most 3 hops in the normal
# case) -- guards against any future bug in the routing logic turning
# into an infinite same-turn loop instead of a clean, logged stop.
MAX_HOPS_PER_TURN = 6

# How long get_known_categories() trusts its cached category list before
# re-querying MySQL (see DATABASE.SQL_CONNECTOR.list_categories).
CATEGORY_CACHE_TTL_SECONDS = 300

_GENERAL_LOBBY_KEY = "_general"

# Sentinel used inside a partial `_merge_dict`-reduced state update to
# mean "remove this key" -- a plain merge can only add/overwrite a key,
# never delete one, and Sales Consultant Agent's redirect needs to clear
# a category's `product` / `pitch_delivered` entry so guardrail_in's
# resume logic correctly sends the next message back to an earlier agent.
# A plain string, not a bare `object()` -- LangGraph's checkpointer
# msgpack-serializes every node's raw pending write (not just the
# reduced value), and an arbitrary Python object isn't serializable.
_REMOVE = "__remove__"


def _merge_dict(base: Optional[dict], update: Optional[dict]) -> dict:
    """LangGraph reducer for the per-category dict state keys
    (business_need, product, candidates, pitch_delivered): merges a
    node's partial {category: value} update into the accumulated dict,
    one key at a time, so a node only ever needs to return the categories
    it actually touched. A value of `_REMOVE` deletes that category's
    entry instead of overwriting it."""
    merged = dict(base) if base else {}
    for key, value in (update or {}).items():
        if value is _REMOVE:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _merge_lobby(base: Optional[dict], update: Optional[dict]) -> dict:
    """LangGraph reducer for the `lobby` state key: merges a node's partial
    {category: [new_turns]} update into the accumulated per-category
    threads, extending each category's own list rather than overwriting
    it (mirrors `history`'s `operator.add`, just keyed by category, and
    per-category rather than deletable like `_merge_dict` above -- a
    conversation log is never retracted)."""
    merged = dict(base) if base else {}
    for category, turns in (update or {}).items():
        merged[category] = merged.get(category, []) + list(turns)
    return merged


def _append(base: Optional[list], update: Optional[list]) -> list:
    """Plain append reducer for `history` / `logs` -- equivalent to
    operator.add for two lists, spelled out so both keys share one
    obviously-correct reducer."""
    return list(base or []) + list(update or [])


class Graph_State(TypedDict):
    question: str
    answer: str
    # This turn's routing decision -- what each node returns instead of a
    # shared router() function reading a fixed `context` enum.
    next: str
    # What the turn's final answer is *about*, kept only for the external
    # API response (ENDPOINTS/endpoints.py's ChatResponse.context) and
    # for tracing -- DECLINE / GREETING / CHAT / BUSINESS_NEED /
    # PRODUCT_CONSULT / RECOMMENDATION.
    context: str
    # The category (or categories) this turn is actually about. Replaced
    # outright whenever the message names a category (possibly more than
    # one), kept as-is on a bare follow-up -- same "sticky until
    # overwritten" behaviour as the old `active_category` field, just
    # always a list now (dynamic multi-product support).
    active_categories: list
    # category -> {budget_max, use_cases, brand, motivation, pain_points,
    # urgency_level, satisfied} -- business need AND customer psychology
    # together, captured once by Business Need Agent and read by every
    # agent downstream instead of re-derived each time.
    business_need: Annotated[dict, _merge_dict]
    # category -> {"top_picks": [...]}, set once Product Expert Agent is
    # satisfied for that category.
    product: Annotated[dict, _merge_dict]
    # category -> the scored candidates hybrid_search returned for it.
    candidates: Annotated[dict, _merge_dict]
    # category -> True once Sales Consultant Agent has actually shown a
    # pitch for it -- this (not `product`) is what tells guardrail_in and
    # Sales Consultant Agent whether the next message on this category is
    # a fresh pitch or a reaction to one already shown.
    pitch_delivered: Annotated[dict, _merge_dict]
    clarification: Optional[bool]
    # Same-turn hop counter (see MAX_HOPS_PER_TURN) -- reset to 0 by
    # guardrail_in at the start of every turn.
    hops: int
    history: Annotated[list, _append]
    lobby: Annotated[dict, _merge_lobby]
    logs: Annotated[list, _append]


_vector_store: Optional[DB_CONNECTOR] = None
_graph = None
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent-pipeline")
_categories_cache = {"value": [], "fetched_at": 0.0}


def get_vector_store() -> DB_CONNECTOR:
    global _vector_store
    if _vector_store is None:
        _vector_store = DB_CONNECTOR()
    return _vector_store


def get_known_categories() -> list:
    """Live category list from the catalog, cached for
    CATEGORY_CACHE_TTL_SECONDS -- a cheap standalone query rather than
    routing through get_vector_store()/DB_CONNECTOR, so a plain greeting
    doesn't force-load the embedding model on the first request."""
    now = time.monotonic()
    if (
        not _categories_cache["value"]
        or now - _categories_cache["fetched_at"] > CATEGORY_CACHE_TTL_SECONDS
    ):
        fetched = list_categories()
        if fetched:
            _categories_cache["value"] = fetched
            _categories_cache["fetched_at"] = now
    return list(_categories_cache["value"])


def _product_noun(category: str) -> str:
    """Category names come straight from the catalog -- lowercased for use
    in prose ("recommend an air conditioner"). Not real singularization,
    just a reasonable default; category names are admin-controlled."""
    return category.strip().lower()


def _build_checkpointer() -> SqliteSaver:
    path = getattr(config, "CHECKPOINT_DB_PATH", "WORKFLOW/checkpoints.sqlite")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def _recent_history_text(history: list) -> str:
    if not history:
        return ""
    recent = history[-MAX_HISTORY_TURNS:]
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


def _lobby_update(categories: Optional[list], role: str, content: str) -> dict:
    """Partial `lobby` update filing one turn (role/content) under EACH of
    `categories`' own conversation thread, or under `_general` when no
    category applies."""
    keys = list(categories) if categories else [_GENERAL_LOBBY_KEY]
    entry = {"role": role, "content": content}
    return {key: [entry] for key in keys}


def _lobby_exchange(categories: Optional[list], question: str, answer: Optional[str]) -> dict:
    """Records one full exchange -- the customer's message AND the
    assistant's reply to it -- under each of `categories`' own thread in
    one shot. Use this (instead of two separate `_lobby_update` calls, or
    a bare user-only one) from any node that ENDS the turn itself
    (business_need_agent / product_expert_agent's not-satisfied returns)
    -- a node that only hands off to a later node in the same turn
    (satisfied path) should keep using plain `_lobby_update(cats, "user",
    question)`, since the eventual answer isn't known yet there and
    whichever node does finish the turn logs its own reply.

    Without this, a category's lobby thread only ever contained the
    customer's own messages back-to-back, with none of *our* follow-up
    questions in between. That broke two things: `_count_consultation_rounds`
    (which requires an assistant turn ending in "?" immediately followed
    by a user turn to count a round at all) always saw zero rounds no
    matter how many times a clarifying question was actually asked, so
    the MIN/MAX round gates in BUSINESS_NEED_AGENT.py could never fire --
    `satisfied` was structurally unreachable and the consultation could
    never converge. It also meant the LLM's own `history` context never
    showed it what it had already asked, inviting repeat questions."""
    keys = list(categories) if categories else [_GENERAL_LOBBY_KEY]
    entries = [{"role": "user", "content": question}]
    if answer:
        entries.append({"role": "assistant", "content": answer})
    return {key: list(entries) for key in keys}


def _lobby_turns(lobby: Optional[dict], categories: Optional[list]) -> list:
    """Raw {role, content} turns for the given categories' own threads
    (or `_general` when none apply), combined in the order they
    happened."""
    lobby = lobby or {}
    combined = []
    for category in (categories or [_GENERAL_LOBBY_KEY]):
        combined.extend(lobby.get(category, []))
    return combined


def _lobby_history_text(lobby: Optional[dict], categories: Optional[list]) -> str:
    return _recent_history_text(_lobby_turns(lobby, categories))


def _count_consultation_rounds(history: list) -> int:
    """Each assistant message that ends with a '?' followed by a user
    reply counts as one consultation round."""
    rounds = 0
    for i, turn in enumerate(history):
        if turn.get("role") == "assistant" and turn.get("content", "").rstrip().endswith("?"):
            if i + 1 < len(history) and history[i + 1].get("role") == "user":
                rounds += 1
    return rounds


BUY_NOW_MARKER_RE = re.compile(
    r"^\s*#{0,6}\s*\**\s*"
    r"(buy now|official purchase link|purchase link|available online|"
    r"where to buy|shop now|buy online|add to cart)"
    r"\s*\**\s*:?\s*$",
    re.IGNORECASE,
)
MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")


def _scrub_invented_purchase_prose(text: Optional[str]) -> Optional[str]:
    """Safety net on top of Sales Consultant Agent's own prompt (which
    already says never to add a Buy Now section): strips one if it shows
    up anyway, and un-markdown-links any stray links, since a dedicated
    purchase card is rendered separately by the frontend from `product`,
    never from prose."""
    if not text:
        return text
    lines = text.split("\n")
    kept = []
    skipping = False
    for line in lines:
        if BUY_NOW_MARKER_RE.match(line):
            skipping = True
            continue
        if skipping:
            if line.strip() == "":
                skipping = False
                continue
            if line.lstrip().startswith("#"):
                skipping = False
            else:
                continue
        kept.append(MD_LINK_RE.sub(r"\1", line))
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _describe_top_picks(product_entry: Optional[dict]) -> str:
    """Readable summary of one category's currently-shown product(s) --
    name, price, specs, and the why_this narrative already on the card --
    for grounding Sales Consultant Agent's answer in exactly what's
    already been shown, nothing more."""
    if not product_entry or not product_entry.get("top_picks"):
        return "(no product currently shown)"
    lines = []
    for pick in product_entry["top_picks"]:
        name = pick.get("name") or "Unknown product"
        price = (pick.get("buy") or {}).get("price")
        specs = pick.get("specs") or {}
        specs_text = ", ".join(f"{key}: {value}" for key, value in specs.items())
        line = f"- {name}"
        if price is not None:
            line += f" (₹{price})"
        if specs_text:
            line += f" -- {specs_text}"
        if pick.get("why_this"):
            line += f"\n  Why recommended: {pick['why_this']}"
        lines.append(line)
    return "\n".join(lines) if lines else "(no product currently shown)"


def _log(agent: str, next_hop: str, **fields) -> dict:
    entry = {"agent": agent, "ts": round(time.time(), 3), "next": next_hop}
    entry.update(fields)
    return entry


def _hop_check(state: Graph_State, agent_name: str, fallback_context: str):
    """Returns (stop_update, hops). stop_update is non-None only when
    MAX_HOPS_PER_TURN is exceeded -- callers should return it immediately.
    Otherwise callers use the returned `hops` count in their own update."""
    hops = int(state.get("hops") or 0) + 1
    if hops > MAX_HOPS_PER_TURN:
        return (
            {
                "next": "guardrail_out",
                "answer": (
                    "Let's take that one step at a time -- could you tell me "
                    "again what you're looking for?"
                ),
                "clarification": True,
                "context": fallback_context,
                "hops": hops,
                "logs": [_log(agent_name, "guardrail_out", reason="hop_budget_exceeded")],
            },
            hops,
        )
    return None, hops


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def guardrail_in(state: Graph_State):
    """Predefined-rules entry gate (AGENTS/GUARDRAIL_AGENT.entry_check) --
    no LLM call. Rejects the cheap, high-confidence bad cases, answers a
    pure greeting with a static message, and otherwise decides where a
    fresh message should resume: business_need (a new/changed category,
    or an existing one not yet satisfied), product_expert (business need
    settled but no product picked yet), or sales_consultant (everything
    active already has a pitch -- this is a reaction to it, or a doubt/
    comparison question, which Sales Consultant Agent itself figures out
    from the message)."""
    question = state["question"]
    history_update = {"history": [{"role": "user", "content": question}]}
    known_categories = get_known_categories()

    check = entry_check(question, known_categories)

    if not check["is_valid"]:
        return {
            "next": "decline",
            "answer": DECLINE_MESSAGE,
            "context": "DECLINE",
            "clarification": False,
            "hops": 0,
            "logs": [_log("guardrail_in", "decline", reason=check["reason"])],
            **history_update,
        }

    active = list(state.get("active_categories") or [])

    if check["is_greeting"] and not active:
        return {
            "next": "greeting",
            "answer": GREETING_MESSAGE,
            "context": "GREETING",
            "clarification": False,
            "hops": 0,
            "logs": [_log("guardrail_in", "greeting")],
            **history_update,
        }

    hints = check["category_hints"]
    merged_active = hints if hints else active

    business_need = state.get("business_need") or {}
    product = state.get("product") or {}

    need_satisfied = all(business_need.get(c, {}).get("satisfied") for c in merged_active)
    product_ready = all(c in product for c in merged_active)

    if not merged_active or not need_satisfied:
        next_hop = "business_need"
    elif not product_ready:
        next_hop = "product_expert"
    else:
        next_hop = "sales_consultant"

    return {
        "next": next_hop,
        "active_categories": merged_active,
        "clarification": False,
        "hops": 0,
        "logs": [_log(
            "guardrail_in", next_hop,
            category_hints=hints,
            active_categories=merged_active,
        )],
        **history_update,
    }


def business_need_agent(state: Graph_State):
    """LLM-backed. One structured call (AGENTS/BUSINESS_NEED_AGENT.assess)
    covering category detection (possibly more than one at once),
    budget/use-case/brand extraction, and psychology intake -- see that
    module's docstring for what it replaces. Hands off to product_expert
    in the SAME turn once satisfied (so a customer who already gave
    enough detail still gets a recommendation in one round trip); ends
    the turn with a follow-up question otherwise."""
    stop, hops = _hop_check(state, "business_need", "BUSINESS_NEED")
    if stop:
        return stop

    question = state["question"]
    active = state.get("active_categories") or []
    known_categories = get_known_categories()
    business_need = state.get("business_need") or {}

    history_text = _lobby_history_text(state.get("lobby"), active or None)
    rounds = _count_consultation_rounds(_lobby_turns(state.get("lobby"), active or None))

    result = business_need_assess(
        question, known_categories,
        history=history_text, consultation_rounds=rounds, company_name=COMPANY_NAME,
        current_categories=active or None,
        store_cities=_store_cities(),
    )

    if not result["is_shopping_request"]:
        return {
            "next": "guardrail_out",
            "answer": result["reply"],
            "context": "CHAT",
            "clarification": False,
            "hops": hops,
            "logs": [_log("business_need", "guardrail_out", reason="not_a_shopping_request")],
            "lobby": _lobby_exchange(active or None, question, result["reply"]),
        }

    llm_categories = result["categories"]
    uncorroborated_switch = False
    if active and llm_categories and not (set(llm_categories) & set(active)):
        # The LLM wants to move to a category that doesn't overlap with
        # the one already established for this conversation. That's
        # sometimes real ("actually, show me headphones instead"), but a
        # small model can also hallucinate a category once the message
        # that originally established it has scrolled out of its history
        # window -- e.g. "brand new model" mid-way through an iPhone
        # conversation getting mis-read as "laptop". Require the raw
        # message itself to contain a cheap rule-based signal for the new
        # category before trusting the switch; otherwise stay put and let
        # the established category keep being what's being discussed.
        corroborated = set(detect_categories(question, known_categories)) & set(llm_categories)
        if not corroborated:
            uncorroborated_switch = True
            logger.info(
                "business_need_agent: ignoring uncorroborated category switch %s -> %s for %r",
                active, llm_categories, question,
            )
            llm_categories = [c for c in llm_categories if c in active] or active

    target_categories = llm_categories or active

    if not target_categories:
        fallback_reply = result["reply"] or f"What are you shopping for today at {COMPANY_NAME}?"
        return {
            "next": "guardrail_out",
            "answer": fallback_reply,
            "context": "BUSINESS_NEED",
            "clarification": True,
            "hops": hops,
            "logs": [_log("business_need", "guardrail_out", reason="no_category_yet")],
            "lobby": _lobby_exchange(None, question, fallback_reply),
        }

    # An uncorroborated switch attempt means the LLM was *not* confident
    # enough to trust for `satisfied` either (it was reasoning about the
    # wrong category) -- fall back to another round on the established
    # category rather than risk recording "satisfied" business-need data
    # under a category the customer never actually asked to switch to.
    satisfied = result["satisfied"] and not uncorroborated_switch

    entry = {
        "budget_max": result["budget_max"],
        "use_cases": result["use_cases"],
        "brand": result["brand"],
        "city": result.get("city"),
        "motivation": result["motivation"],
        "pain_points": result["pain_points"],
        "urgency_level": result["urgency_level"],
        "satisfied": satisfied,
    }
    need_update = {cat: entry for cat in target_categories}
    new_active = list(dict.fromkeys(list(active) + target_categories)) if active else target_categories
    # A message that named its own category(ies) replaces the active set
    # (mirrors guardrail_in's own hint-based replace); a bare "yes"/"under
    # 50000" that arrived here with no fresh hints just fills in the
    # existing active category instead of appending to it.
    if llm_categories:
        new_active = target_categories

    if satisfied:
        return {
            "next": "product_expert",
            "active_categories": new_active,
            "business_need": need_update,
            "context": "BUSINESS_NEED",
            "clarification": False,
            "hops": hops,
            "logs": [_log("business_need", "product_expert", categories=target_categories)],
            # No final answer yet this turn (product_expert/sales_consultant
            # still to run) -- just record the customer's message.
            "lobby": _lobby_update(target_categories, "user", question),
        }

    reply = result["reply"]
    if uncorroborated_switch:
        # Don't surface the LLM's reply (it was written about the wrong
        # category) -- ask a plain, category-agnostic follow-up instead.
        reply = (
            "Just to make sure I keep helping with the right thing -- "
            "could you tell me a bit more about what you're looking for?"
        )

    return {
        "next": "guardrail_out",
        "active_categories": new_active,
        "business_need": need_update,
        "answer": reply,
        "context": "BUSINESS_NEED",
        "clarification": True,
        "hops": hops,
        "logs": [_log("business_need", "guardrail_out", categories=target_categories, satisfied=False)],
        # This node is ending the turn itself -- log BOTH halves of the
        # exchange (see _lobby_exchange's docstring for why the old
        # user-only version broke round counting).
        "lobby": _lobby_exchange(target_categories, question, reply),
    }


def product_expert_agent(state: Graph_State):
    """LLM-backed. Runs hybrid_search + one structured recommendation call
    (AGENTS/PRODUCT_EXPERT_AGENT.recommend) per category not yet product-
    satisfied -- grounded only in that category's own retrieved
    candidates, same as the old CrewAI product agent was. Hands off to
    sales_consultant in the SAME turn once every active category is
    satisfied; otherwise ends the turn (a consulting question, or -- if
    the customer's message rejected the current direction outright -- an
    acknowledgement, with that category's business need marked
    unsatisfied so the next message resumes at business_need)."""
    stop, hops = _hop_check(state, "product_expert", "PRODUCT_CONSULT")
    if stop:
        return stop

    question = state["question"]
    active = state.get("active_categories") or []
    business_need = state.get("business_need") or {}
    product = state.get("product") or {}

    targets = [c for c in active if c not in product] or list(active)

    replies = []
    all_satisfied = True
    product_update = {}
    candidates_update = {}
    need_update = {}

    for category in targets:
        product_noun = _product_noun(category)
        need = business_need.get(category, {})
        psychology = {
            "motivation": need.get("motivation"),
            "pain_points": need.get("pain_points"),
            "urgency_level": need.get("urgency_level"),
        }
        history_text = _lobby_history_text(state.get("lobby"), [category])

        db = get_vector_store().vector_database()
        cat_candidates = hybrid_search(
            db, question,
            {
                "budget_max": need.get("budget_max"),
                "use_cases": need.get("use_cases"),
                "brand": need.get("brand"),
            },
            top_k=5, category=category,
        )
        rag_data = format_candidates_for_prompt(cat_candidates)

        # If customer specified a city, boost candidates available there
        customer_city = (need.get("city") or "").strip().lower()
        if customer_city and cat_candidates:
            for cand in cat_candidates:
                offline = str(cand.get("offline_availability") or "").lower()
                if customer_city in offline or any(
                    customer_city in str(s.get("city", "")).lower()
                    for s in (getattr(config, "STORE_LOCATIONS", None) or [])
                    if any(token in offline for token in str(s.get("name", "")).lower().split())
                ):
                    # Boost the overall score slightly for city match
                    scores = cand.get("_scores", {})
                    scores["overall"] = min(1.0, scores.get("overall", 0) + 0.05)
            # Re-sort after city boost
            cat_candidates.sort(
                key=lambda c: c.get("_scores", {}).get("overall", 0.0),
                reverse=True,
            )
            rag_data = format_candidates_for_prompt(cat_candidates)

        result = product_expert_recommend(
            question, category, product_noun,
            business_need=need, customer_psychology=psychology,
            history=history_text, rag_data=rag_data, company_name=COMPANY_NAME,
        )

        candidates_update[category] = cat_candidates

        if result["satisfied"]:
            top_picks = build_top_picks(cat_candidates, result["narratives"])
            # Ensure every pick has a why_this -- fill from specs if
            # the LLM narrative didn't match (prevents the frontend's
            # "No verified reasoning available yet" placeholder)
            for pick in top_picks:
                if not pick.get("why_this"):
                    specs = pick.get("specs") or {}
                    name = pick.get("name") or "This product"
                    spec_highlights = ", ".join(
                        f"{k}: {v}" for k, v in list(specs.items())[:4]
                        if v not in (None, "")
                    )
                    pick["why_this"] = (
                        f"{name} is a strong match based on your requirements."
                        + (f" Key specs: {spec_highlights}." if spec_highlights else "")
                    )
            product_update[category] = {"top_picks": top_picks}
        else:
            all_satisfied = False
            if result["reply"]:
                replies.append(result["reply"])
            if result["wants_new_search"]:
                need_update[category] = {**need, "satisfied": False}

    next_hop = "sales_consultant" if all_satisfied else "guardrail_out"

    update = {
        "next": next_hop,
        "product": product_update,
        "candidates": candidates_update,
        "business_need": need_update,
        "clarification": not all_satisfied,
        "context": "PRODUCT_CONSULT",
        "hops": hops,
        "logs": [_log("product_expert", next_hop, categories=targets, satisfied=all_satisfied)],
    }
    if all_satisfied:
        # No final answer yet this turn (sales_consultant still to run) --
        # just record the customer's message.
        update["lobby"] = _lobby_update(targets, "user", question)
    else:
        # This node is ending the turn itself -- log BOTH halves of the
        # exchange (see _lobby_exchange's docstring: recording only the
        # user's half left this category's lobby thread with no assistant
        # turn to pair against, breaking round counting the same way it
        # broke business_need_agent's).
        answer_text = "\n\n".join(r for r in replies if r) or (
            "Could you tell me a bit more about what you're looking for?"
        )
        update["answer"] = answer_text
        update["lobby"] = _lobby_exchange(targets, question, answer_text)
    return update


def sales_consultant_agent(state: Graph_State):
    """LLM-backed. One structured call per active category
    (AGENTS/SALES_CONSULTANT_AGENT.consult) -- the first time, a full
    storytelling pitch + comparison; on any later visit (guardrail_in
    resumed here because a pitch was already shown), a direct answer to a
    doubt/comparison question, or a redirect that clears this category's
    `product` / `pitch_delivered` (and, for a whole different category,
    marks its business need unsatisfied) so the customer's NEXT message
    resumes at the right earlier agent -- see ORCHE.py's module docstring
    for why that redirect is next-turn rather than a same-turn loop."""
    stop, hops = _hop_check(state, "sales_consultant", "RECOMMENDATION")
    if stop:
        return stop

    question = state["question"]
    active = state.get("active_categories") or []
    business_need = state.get("business_need") or {}
    product = state.get("product") or {}
    pitch_delivered = state.get("pitch_delivered") or {}

    answers = []
    pitch_update = {}
    product_update = {}
    need_update = {}
    redirected = []

    for category in active:
        entry = product.get(category)
        if not entry:
            continue  # guardrail_in only routes here once every active
            # category already has a product entry.

        need = business_need.get(category, {})
        psychology = {
            "motivation": need.get("motivation"),
            "pain_points": need.get("pain_points"),
            "urgency_level": need.get("urgency_level"),
        }
        history_text = _lobby_history_text(state.get("lobby"), [category])
        already_pitched = bool(pitch_delivered.get(category))

        result = sales_consultant_consult(
            question, category,
            business_need=need, customer_psychology=psychology,
            product_summary=_describe_top_picks(entry),
            history=history_text, pitch_delivered=already_pitched,
            company_name=COMPANY_NAME,
        )

        answers.append((category, result["answer"]))

        if result["next"] == "product_expert":
            product_update[category] = _REMOVE
            pitch_update[category] = _REMOVE
            redirected.append(category)
            # If the customer named a new brand, update business_need
            # so the next product_expert search uses it
            detected_brand = result.get("detected_brand")
            if detected_brand:
                need_update[category] = {**need, "brand": detected_brand}
        elif result["next"] == "business_need":
            product_update[category] = _REMOVE
            pitch_update[category] = _REMOVE
            need_update[category] = {**need, "satisfied": False}
            redirected.append(category)
        else:
            pitch_update[category] = True

    if len(active) > 1 and len(answers) > 1:
        combined = "\n\n---\n\n".join(f"## {cat.title()}\n\n{text}" for cat, text in answers)
    elif answers:
        combined = answers[0][1]
    else:
        combined = DECLINE_MESSAGE

    # Deliberately NOT substituting DECLINE_MESSAGE here for an empty/
    # scrubbed-to-nothing answer -- guardrail_out is the single place
    # that decides an answer isn't good enough to show and relabels
    # `context` to DECLINE accordingly; doing it here too would leave an
    # empty answer showing as context="RECOMMENDATION".
    combined = _scrub_invented_purchase_prose(combined) or ""

    lobby_update = _lobby_update(active, "assistant", combined)
    lobby_update.setdefault(_GENERAL_LOBBY_KEY, [])

    return {
        "next": "guardrail_out",
        "answer": combined,
        "product": product_update,
        "pitch_delivered": pitch_update,
        "business_need": need_update,
        "clarification": False,
        "context": "RECOMMENDATION",
        "hops": hops,
        "logs": [_log("sales_consultant", "guardrail_out", categories=active, redirected=redirected)],
        "lobby": lobby_update,
    }


def guardrail_out(state: Graph_State):
    """Predefined-rules exit gate (AGENTS/GUARDRAIL_AGENT.exit_check) --
    no LLM call. Swaps in a safe fallback only on the cheap, high-
    confidence failure modes: an empty answer, or a raw JSON/traceback
    leak. Also where the assistant's final answer for this turn is
    appended to `history` (the old exit_gaurd_agent's job)."""
    # Check the RAW answer (possibly empty/None) -- substituting
    # DECLINE_MESSAGE before the check would let an empty answer sail
    # through as "passed" while still leaving `context` saying
    # RECOMMENDATION/BUSINESS_NEED/etc.
    answer = state.get("answer")
    candidates = state.get("candidates")

    check = exit_check(answer, candidates)

    if not check["passed"]:
        logger.warning("guardrail_out rejected an answer: %s", check["reason"])
        final_answer = DECLINE_MESSAGE
        update = {
            "answer": final_answer,
            "context": "DECLINE",
            "logs": [_log("guardrail_out", "end", passed=False, reason=check["reason"])],
        }
    else:
        final_answer = answer
        update = {"logs": [_log("guardrail_out", "end", passed=True)]}

    update["history"] = [{"role": "assistant", "content": final_answer}]
    return update


def _route_from_guardrail_in(state: Graph_State):
    return state.get("next", "business_need")


def _route_from_business_need(state: Graph_State):
    return state.get("next", "guardrail_out")


def _route_from_product_expert(state: Graph_State):
    return state.get("next", "guardrail_out")


def get_graph():
    global _graph
    if _graph is not None:
        return _graph

    builder = StateGraph(Graph_State)

    builder.add_node("guardrail_in", guardrail_in)
    builder.add_node("business_need", business_need_agent)
    builder.add_node("product_expert", product_expert_agent)
    builder.add_node("sales_consultant", sales_consultant_agent)
    builder.add_node("guardrail_out", guardrail_out)

    builder.add_edge(START, "guardrail_in")

    builder.add_conditional_edges(
        "guardrail_in",
        _route_from_guardrail_in,
        {
            "decline": END,
            "greeting": END,
            "business_need": "business_need",
            "product_expert": "product_expert",
            "sales_consultant": "sales_consultant",
        },
    )

    builder.add_conditional_edges(
        "business_need",
        _route_from_business_need,
        {"product_expert": "product_expert", "guardrail_out": "guardrail_out"},
    )

    builder.add_conditional_edges(
        "product_expert",
        _route_from_product_expert,
        {"sales_consultant": "sales_consultant", "guardrail_out": "guardrail_out"},
    )

    # Sales Consultant's own `next` (done / product_expert / business_need)
    # only ever adjusts *persistent* state for the customer's next
    # message -- this turn always finishes through guardrail_out, so this
    # is a plain edge, not a conditional one.
    builder.add_edge("sales_consultant", "guardrail_out")

    builder.add_edge("guardrail_out", END)

    _graph = builder.compile(checkpointer=_build_checkpointer())
    return _graph


def _confidence_from(candidates: Optional[dict]) -> Optional[float]:
    """Best active candidate's own deterministic score -- there's no LLM
    evaluation score anymore (guardrail_out is rule-based pass/fail, not
    a 0-1 grade), so this is the only signal left, same as it was for the
    old pipeline's fallback path."""
    flat = [item for value in (candidates or {}).values() for item in (value or [])]
    if not flat:
        return None
    best = max(flat, key=lambda c: c.get("_scores", {}).get("overall", 0.0))
    return best.get("_scores", {}).get("overall")


def _shape_product_for_api(active: list, product: dict) -> Optional[dict]:
    """External contract (unchanged from the CrewAI-based pipeline): a
    single active category returns `product` flat ({"top_picks": [...]});
    more than one returns {category: {...}}. Internally `product` is
    always category-keyed -- this is only for the API response."""
    shown = {cat: product[cat] for cat in active if cat in product}
    if not shown:
        return None
    if len(active) == 1:
        return shown[active[0]]
    return shown


def _invoke(question: str, thread_id: str) -> dict:
    tracer = TraceBuilder(thread_id, question)
    graph = get_graph()

    result = graph.invoke(
        {"question": question},
        config={"configurable": {"thread_id": thread_id}},
    )

    active = result.get("active_categories") or []
    candidates = {cat: result["candidates"][cat] for cat in active if cat in (result.get("candidates") or {})} or None
    product_data = _shape_product_for_api(active, result.get("product") or {})
    context = result.get("context", "CHAT")

    tracer.add(
        context=context,
        active_categories=active,
        business_need={cat: result.get("business_need", {}).get(cat) for cat in active},
        logs=result.get("logs"),
    )
    tracer.finish()

    if context == "RECOMMENDATION" and product_data:
        response_type = "recommendation"
    elif result.get("clarification"):
        response_type = "clarification"
    else:
        response_type = "normal"

    return {
        "answer": result.get("answer", DECLINE_MESSAGE),
        "context": context,
        "response_type": response_type,
        "product": product_data,
        "candidates": candidates,
        "confidence": _confidence_from(candidates),
    }


def ask(question: str, thread_id: str = "default") -> dict:
    timeout = getattr(config, "REQUEST_TIMEOUT_SECONDS", 90)
    future = _executor.submit(_invoke, question, thread_id)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        raise TimeoutError(f"Agent pipeline timed out after {timeout}s") from None


def get_history(thread_id: str) -> list:
    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    return list((snapshot.values or {}).get("history", []))
