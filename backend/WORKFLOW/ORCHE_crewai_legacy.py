import itertools
import json
import logging
import operator
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

from AGENTS.CHATBOT_AGENT import CHATBOT_AGENT
from AGENTS.CLARIFICATION_AGENT import (
    assess_clarity,
    assess_followup_intent,
    assess_result_quality,
    assess_sufficiency,
    MIN_CONSULTATION_ROUNDS,
)
from AGENTS.ENTRYSAFEGAURD_AGENT import isvalidquery as entry_guard_check
from AGENTS.EXIT_SAFE_GAURD_AGENT import evaluate_response
from AGENTS.REQUIREMENT_EXTRACTOR_AGENT import extract_requirements
from AGENTS.SALES_CREW_FACTORY import build_sales_crew

from DATABASE.SQL_CONNECTOR import DB_CONNECTOR, list_categories
from WORKFLOW.recommendations import build_top_picks
from WORKFLOW.retrieval import format_candidates_for_prompt, hybrid_search
from WORKFLOW.tracing import TraceBuilder


logger = logging.getLogger("agentic_salesman.orche")

COMPANY_NAME = getattr(config, "COMPANY_NAME", "Trein")

DECLINE_MESSAGE = (
    f"Sorry, I can only help with questions about the products {COMPANY_NAME} sells."
)

GREETING_MESSAGE = (
    f"Hi there! I'm the {COMPANY_NAME} shopping assistant. Ask me about "
    f"anything we sell -- mobiles, laptops, TVs, appliances and more -- "
    f"and I'll help you find the right one."
)

MAX_HISTORY_TURNS = 6

# How long get_known_categories() trusts its cached category list before
# re-querying MySQL (see DATABASE.SQL_CONNECTOR.list_categories). Categories
# change rarely (a catalog/admin edit, not per-request), so a 5-minute cache
# avoids a DB round trip on every single chat turn -- including plain
# greetings -- while still picking up a newly-added category well within
# one support shift.
CATEGORY_CACHE_TTL_SECONDS = 300


def _merge_lobby(base: Optional[dict], update: Optional[dict]) -> dict:
    """LangGraph reducer for the `lobby` state key: merges a node's partial
    {category: [new_turns]} update into the accumulated per-category
    threads, extending each category's own list rather than overwriting
    it (mirrors `history`'s `operator.add`, just keyed by category)."""

    merged = dict(base) if base else {}

    for category, turns in (update or {}).items():
        merged[category] = merged.get(category, []) + list(turns)

    return merged


class Graph_State(TypedDict):
    question: str
    answer: str
    context: str
    categories: list
    # The category (or categories) most recently confirmed for this thread.
    # Not reset each turn like `categories` above -- LangGraph keeps a plain
    # (non-Annotated) state key's last written value across turns, so once
    # set here it survives until a node explicitly overwrites it. Lets a
    # short follow-up reply ("yes", "macos m1 chip", "show the details")
    # that doesn't itself name a category resume the same recommendation
    # instead of the entry guard treating it as a brand-new, category-less
    # message (see entry_gaurd_agent below).
    active_category: Optional[list]
    product: Optional[dict]
    candidates: Optional[dict]
    requirements: Optional[dict]
    evaluation: Optional[dict]
    clarification: Optional[bool]
    retries: int
    history: Annotated[list, operator.add]
    # Per-category conversation threads -- e.g. {"mobile": [...], "laptop":
    # [...]}. `history` above is the flat, whole-thread log kept only for
    # the public get_history() API/UI (its shape is an external contract,
    # tested by test_history_accumulates_across_turns_on_the_same_thread).
    # Everything that builds context FOR the model (consultation-round
    # counting, requirement extraction, the sufficiency check, the crew's
    # own "conversation history" prompt section) reads `lobby` instead, so
    # asking about a phone right after a fridge doesn't leak fridge
    # back-and-forth into the phone thread's context (or vice versa) --
    # see _lobby_update/_lobby_history_text below.
    lobby: Annotated[dict, _merge_lobby]


_GENERAL_LOBBY_KEY = "_general"


def _lobby_update(categories: Optional[list], role: str, content: str) -> dict:
    """Partial `lobby` update filing one turn (role/content) under EACH of
    `categories`' own conversation thread, or under `_general` when no
    category applies -- greetings, chit-chat, declined queries, and "which
    category?" clarifications that haven't named one yet."""

    keys = list(categories) if categories else [_GENERAL_LOBBY_KEY]
    entry = {"role": role, "content": content}

    return {key: [entry] for key in keys}


def _lobby_history_text(lobby: Optional[dict], categories: Optional[list]) -> str:
    """Recent conversation text scoped to one turn's own category (or
    categories, for a multi-category ask) -- drawn only from those
    categories' threads in `lobby`, never a sibling product's unrelated
    conversation."""

    lobby = lobby or {}
    combined = []

    for category in (categories or [_GENERAL_LOBBY_KEY]):
        combined.extend(lobby.get(category, []))

    return _recent_history_text(combined)


_vector_store: Optional[DB_CONNECTOR] = None
_graph = None
_executor = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="agent-pipeline"
)

# One CrewAI crew per category, built lazily and reused -- building a crew
# is cheap (Agent/Task/Crew are just Python objects; nothing calls the LLM
# until .kickoff()), so this only saves the trivial cost of re-constructing
# the same prompts/tools on every turn, not an LLM call. Replaces the old
# fixed MOBILE/LAPTOP/HEADPHONE AGENT_FUNCS dict -- any category the
# catalog has works the same way, with no code change here.
_crew_cache = {}

_categories_cache = {"value": [], "fetched_at": 0.0}


def get_vector_store() -> DB_CONNECTOR:
    global _vector_store

    if _vector_store is None:
        _vector_store = DB_CONNECTOR()

    return _vector_store


def get_known_categories() -> list:
    """Live category list from the catalog (DATABASE.SQL_CONNECTOR.list_categories),
    cached for CATEGORY_CACHE_TTL_SECONDS. Used by the entry guard (to know
    what it's allowed to route to) and clarify_category (to suggest
    examples) -- deliberately a *cheap* standalone query rather than routing
    through get_vector_store()/DB_CONNECTOR, so a plain greeting doesn't
    force-load the embedding model on the first request of a session."""
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


def _normalize_categories(returned: list, known: list) -> list:
    """Keeps only categories the entry guard's LLM call actually named that
    also exist in the live catalog (case-insensitive), in the catalog's own
    casing -- guards against a hallucinated category ever reaching
    retrieval/CrewAI."""
    lookup = {str(c).strip().lower(): c for c in known}
    normalized = []
    seen = set()

    for item in returned or []:
        match = lookup.get(str(item).strip().lower())
        if match and match not in seen:
            seen.add(match)
            normalized.append(match)

    return normalized


def _product_noun(category: str) -> str:
    """Category names come straight from the catalog (already
    human-readable, e.g. "Mobile", "Refrigerator", "Air Conditioner") --
    lowercased for use in prose ("recommend an air conditioner"). Not real
    singularization, just a reasonable default; a catalog category name is
    admin-controlled, so this is a deliberate simplification, not a
    language model."""
    return category.strip().lower()


def _get_crew(category: str):
    key = category.strip().lower()

    if key not in _crew_cache:
        _crew_cache[key] = build_sales_crew(
            category=category.strip().title(),
            product_noun=_product_noun(category),
        )

    return _crew_cache[key]


def _build_checkpointer() -> SqliteSaver:
    path = getattr(
        config,
        "CHECKPOINT_DB_PATH",
        "WORKFLOW/checkpoints.sqlite",
    )

    os.makedirs(
        os.path.dirname(path) or ".",
        exist_ok=True,
    )

    conn = sqlite3.connect(
        path,
        check_same_thread=False,
    )

    conn.execute("PRAGMA busy_timeout = 5000")

    saver = SqliteSaver(conn)
    saver.setup()

    return saver


def _recent_history_text(history: list) -> str:
    if not history:
        return ""

    recent = history[-MAX_HISTORY_TURNS:]

    return "\n".join(
        f"{turn['role']}: {turn['content']}"
        for turn in recent
    )


def _build_user_request(state: Graph_State, category: str) -> str:
    history_text = _lobby_history_text(
        state.get("lobby"), [category]
    )

    question = state["question"]

    if not history_text:
        return question

    return (
        f"Conversation history:\n"
        f"{history_text}\n\n"
        f"Current customer message:\n"
        f"{question}"
    )


BUY_NOW_MARKER_RE = re.compile(
    r"^\s*#{0,6}\s*\**\s*"
    r"(buy now|official purchase link|purchase link|available online|"
    r"where to buy|shop now|buy online|add to cart)"
    r"\s*\**\s*:?\s*$",
    re.IGNORECASE,
)

MD_LINK_RE = re.compile(
    r"\[([^\]\n]*)\]\([^)\n]*\)"
)


def _scrub_invented_purchase_prose(
    text: Optional[str],
) -> Optional[str]:

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

        kept.append(
            MD_LINK_RE.sub(
                r"\1",
                line,
            )
        )

    cleaned = "\n".join(kept)

    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    )

    return cleaned.strip()


def _extract_product_json(
    raw_text: Optional[str],
) -> Optional[dict]:

    if not raw_text:
        return None

    text = raw_text.strip()

    fence_match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        text,
        re.DOTALL,
    )

    if fence_match:
        text = fence_match.group(1)

    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _narratives_from_parsed(
    parsed: Optional[dict],
) -> Optional[list]:

    if not isinstance(parsed, dict):
        return None

    picks = parsed.get("top_picks")

    if isinstance(picks, list) and picks:
        return picks

    if parsed.get("name"):
        return [parsed]

    return None


def _flatten_candidates(
    candidates_by_category: Optional[dict],
) -> list:

    if not candidates_by_category:
        return []

    return list(
        itertools.chain.from_iterable(
            candidates_by_category.values()
        )
    )


def _top_pick_names(product: Optional[dict]) -> list:
    """Every product name currently shown to the customer, whichever shape
    `product` is in -- a single category's {"top_picks": [...]} or a
    multi-category {category: {"top_picks": [...]}} map (see
    _compose_results). Used to gate/ground assess_followup_intent and
    product_followup: an empty list means nothing has been shown yet, so
    there's nothing for a follow-up question to be about."""

    if not product:
        return []

    if isinstance(product.get("top_picks"), list):
        picks = product["top_picks"]
    else:
        picks = [
            pick
            for value in product.values()
            if isinstance(value, dict)
            for pick in (value.get("top_picks") or [])
        ]

    return [pick.get("name") for pick in picks if pick.get("name")]


def _describe_top_picks(product: Optional[dict]) -> str:
    """Readable summary of the product(s) currently shown to the customer
    -- name, price, key specs, and the why_this narrative already on the
    card -- for grounding product_followup's answer in exactly what's
    already been shown, nothing more."""

    if not product:
        return "(no product currently shown)"

    if isinstance(product.get("top_picks"), list):
        picks = product["top_picks"]
    else:
        picks = [
            pick
            for value in product.values()
            if isinstance(value, dict)
            for pick in (value.get("top_picks") or [])
        ]

    lines = []

    for pick in picks:
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


def _compose_results(results: list) -> tuple:
    """Returns (answer_text, product_by_category_or_None, candidates_by_category,
    all_clarification). `all_clarification` is True only when EVERY
    category's result was a clarifying question rather than a real
    recommendation (see AGENTS/CLARIFICATION_AGENT.py) -- that's what tells
    exit_gaurd_agent it can skip the (otherwise pointless) quality
    evaluation for this turn."""

    all_clarification = bool(results) and all(
        result.get("clarification") for result in results
    )

    if len(results) == 1:

        result = results[0]

        return (
            result["text"],
            result["product"],
            {
                result["category"]: result["candidates"]
            },
            all_clarification,
        )

    sections = []
    products = {}
    candidates_by_category = {}

    for result in results:

        label = result["category"].title()

        sections.append(
            f"## {label}\n\n{result['text']}"
        )

        if result["product"]:
            products[result["category"]] = result["product"]

        candidates_by_category[
            result["category"]
        ] = result["candidates"]

    return (
        "\n\n---\n\n".join(sections),
        products or None,
        candidates_by_category,
        all_clarification,
    )


def entry_gaurd_agent(state: Graph_State):

    question = state["question"]

    history = state.get("history", [])

    history_update = {
        "history": [
            {
                "role": "user",
                "content": question,
            }
        ]
    }

    known_categories = get_known_categories()

    valid = entry_guard_check(question, known_categories)

    if not valid.get("query"):
        return {
            "context": "DENY",
            "categories": [],
            "lobby": _lobby_update(None, "user", question),
            **history_update,
        }

    categories = _normalize_categories(
        valid.get("categories"), known_categories
    )

    if categories:

        return {
            "context": "RECOMMENDATION",
            "categories": categories,
            "active_category": categories,
            "lobby": _lobby_update(categories, "user", question),
            **history_update,
        }

    active_category = state.get("active_category")

    if active_category and valid.get("query") and not valid.get("greeting"):
        # This message doesn't name a category on its own -- it could be a
        # spec ("macos m1 chip"), a plain confirmation ("yes please"), or a
        # follow-up request ("show the details") -- but there's already an
        # active_category for this thread and nothing here reads as
        # off-topic or a fresh greeting. Earlier this only fired right
        # after a clarifying *question* (checking the previous turn ended
        # in "?"), which broke as soon as the assistant answered with a
        # plain statement instead of a question (e.g. "One moment while I
        # retrieve those details!") -- the very next reply would then fall
        # through to a generic chat answer or "what are you shopping for?",
        # silently dropping the category the customer already gave. So this
        # now stays on the active category for the rest of the thread,
        # until the customer's message itself names a different one (which
        # the `if categories:` branch above already takes priority over).
        # Before committing to a fresh search, check whether this reads
        # as a doubt/opinion/comparison question about the product(s)
        # ALREADY shown for this category, rather than a new or changed
        # requirement -- e.g. "what do you think about the Noise Buds"
        # after already recommending it. Only worth asking when there's
        # actually a shown product to be a follow-up about; the extra LLM
        # call is skipped entirely otherwise (first turn in a category,
        # or right after a clarifying question with no product yet).
        shown_product_names = _top_pick_names(state.get("product"))

        if shown_product_names:

            followup = assess_followup_intent(
                question,
                product_names=shown_product_names,
                history=_lobby_history_text(
                    state.get("lobby"), active_category
                ),
                company_name=COMPANY_NAME,
            )

            if followup.get("is_followup"):

                return {
                    "context": "PRODUCT_FOLLOWUP",
                    "categories": active_category,
                    "clarification": False,
                    "lobby": _lobby_update(active_category, "user", question),
                    **history_update,
                }

        return {
            "context": "RECOMMENDATION",
            "categories": active_category,
            "lobby": _lobby_update(active_category, "user", question),
            **history_update,
        }

    if valid.get("wants_recommendation_but_unclear") and known_categories:

        return {
            "context": "CLARIFY_CATEGORY",
            "categories": [],
            "lobby": _lobby_update(None, "user", question),
            **history_update,
        }

    # A bare "greeting" classification only means a fresh hello when there
    # is no conversation yet. Mid-conversation, a short reply like "yes"/
    # "sure"/"ok" answering a prior clarifying question can also read as
    # generic small talk to the (context-free) entry guard classifier --
    # routing that to the hardcoded GREETING_MESSAGE would silently wipe
    # out the in-progress conversation instead of continuing it. So once
    # there's history, always keep going through the context-aware CHAT
    # path instead of resetting to the canned greeting.
    if valid.get("greeting") and not history:

        return {
            "context": "GREETING",
            "categories": [],
            "lobby": _lobby_update(None, "user", question),
            **history_update,
        }

    return {
        "context": "CHAT",
        "categories": [],
        "lobby": _lobby_update(None, "user", question),
        **history_update,
    }


def router(state: Graph_State):

    context = state.get("context")

    if context == "RECOMMENDATION":
        return "sales_agents"

    if context == "PRODUCT_FOLLOWUP":
        return "product_followup"

    if context == "CLARIFY_CATEGORY":
        return "clarify_category"

    if context == "GREETING":
        return "greeting"

    if context == "CHAT":
        return "chatbot"

    return "chatbot"


def chatbot(state: Graph_State):

    history = _recent_history_text(
        state.get("history", [])
    )

    question = state["question"]

    prompt = f"""
You are a helpful conversational shopping assistant for {COMPANY_NAME}.

You can discuss anything {COMPANY_NAME} sells.

Do not recommend a specific product unless the user explicitly asks
for a recommendation or clearly indicates that they want to buy/select
a product.

Use the previous conversation to understand follow-up questions.

Previous conversation:
{history}

Current user message:
{question}

Respond naturally as a chatbot.
"""

    try:

        result = CHATBOT_AGENT(prompt)

        answer = getattr(
            result,
            "raw",
            None,
        ) or str(result)

        return {
            "answer": answer.strip(),
            "product": None,
            "candidates": None,
        }

    except Exception as exc:

        logger.exception(
            "Chatbot failed: %s",
            exc,
        )

        return {
            "answer": DECLINE_MESSAGE,
            "product": None,
            "candidates": None,
        }


def product_followup(state: Graph_State):
    """Answers a doubt/opinion/comparison question about the product(s)
    already shown for the active category -- WITHOUT re-running
    hybrid_search or the sales crew. entry_gaurd_agent only routes here
    once assess_followup_intent has confirmed the message reads as a
    follow-up rather than a fresh requirement (see there). Deliberately
    leaves `product`/`candidates` untouched in its return so a chain of
    follow-up questions keeps working -- see _top_pick_names' gate in
    entry_gaurd_agent, which needs state["product"] to still hold the
    last real recommendation, not None."""

    question = state["question"]
    active_category = state.get("active_category") or []

    history_text = _lobby_history_text(
        state.get("lobby"), active_category
    )

    picks_text = _describe_top_picks(state.get("product"))

    prompt = f"""
You are a helpful shopping assistant for {COMPANY_NAME}.

The customer was just shown these product(s):
{picks_text}

Conversation so far:
{history_text}

Current customer message:
{question}

Answer their question using ONLY the product details already shown
above -- do not invent specs, prices, or features that aren't listed.
If they ask to compare the shown products, compare only those. If they
ask about something the shown products don't cover, say so honestly
rather than guessing. Do not recommend a different product unless they
explicitly ask for alternatives. Respond naturally, in 2-4 sentences.
"""

    try:

        result = CHATBOT_AGENT(prompt)

        answer = getattr(
            result,
            "raw",
            None,
        ) or str(result)

        answer = answer.strip()

    except Exception as exc:

        logger.exception(
            "Product follow-up answer failed: %s",
            exc,
        )

        answer = DECLINE_MESSAGE

    return {
        "answer": answer,
    }


def greeting(state: Graph_State):

    return {
        "answer": GREETING_MESSAGE,
        "product": None,
        "candidates": None,
    }


def clarify_category(state: Graph_State):
    """Reached when the entry guard is confident the customer wants
    shopping help but couldn't tell (or the message doesn't say) which
    category -- e.g. "help me pick something nice for my new kitchen".
    Part of task 1.1: ask instead of guessing which category, rather than
    silently falling through to CHAT or DENY."""

    known_categories = get_known_categories()

    examples = ", ".join(known_categories[:8]) if known_categories else (
        "mobiles, laptops, TVs, refrigerators and more"
    )

    answer = (
        f"Happy to help you find the right product at {COMPANY_NAME}! "
        f"What are you shopping for today -- {examples}, or something else?"
    )

    return {
        "answer": answer,
        "product": None,
        "candidates": None,
    }



def _count_consultation_rounds(history: list) -> int:
    """Count how many clarification/consultation exchanges have happened.
    Each assistant message that ends with a '?' (a question) followed by
    a user reply counts as one consultation round. This tells the
    clarification agent how many times we've already asked the customer
    for more info before this turn."""
    rounds = 0
    for i, turn in enumerate(history):
        if (
            turn.get("role") == "assistant"
            and turn.get("content", "").rstrip().endswith("?")
        ):
            # Check if there's a subsequent user reply
            if i + 1 < len(history) and history[i + 1].get("role") == "user":
                rounds += 1
    return rounds


def _run_one_category(
    state: Graph_State,
    category: str,
    requirements: dict,
    retry_feedback: Optional[str] = None,
    check_clarity: bool = True,
) -> dict:

    query = state["question"]
    product_noun = _product_noun(category)

    user_request = _build_user_request(state, category)

    if retry_feedback:

        user_request += (
            f"\n\nPrevious answer failed quality review because: "
            f"{retry_feedback}\n"
            f"Generate a corrected answer using only the RAG data."
        )

    # Scoped to THIS category's own thread -- not the whole (possibly
    # multi-product) conversation -- so a round of back-and-forth about a
    # fridge earlier in the same session doesn't count as consultation
    # rounds for a phone asked about afterwards, and vice versa.
    category_history = state.get("lobby", {}).get(category, [])
    consultation_rounds = _count_consultation_rounds(category_history)
    history_text = _recent_history_text(category_history)

    # Gate the vector DB call itself, not just the crew below it: decide
    # whether the customer has said enough to be worth searching for
    # BEFORE touching hybrid_search/Chroma, not after. Retries skip this
    # check entirely: by then we're already committed to producing a
    # better answer using the evaluator's feedback, not asking a fresh
    # question.
    if check_clarity and retry_feedback is None:

        sufficiency = assess_sufficiency(
            query,
            product_noun,
            requirements=requirements,
            company_name=COMPANY_NAME,
            consultation_rounds=consultation_rounds,
            history=history_text,
        )

        if sufficiency["needs_clarification"]:

            # [] (never None) -- _compose_results/_flatten_candidates
            # chain.from_iterable()s every category's candidate list
            # together, which raises on a bare None.
            return {
                "category": category,
                "text": sufficiency["question"],
                "product": None,
                "candidates": [],
                "clarification": True,
            }

    db = get_vector_store().vector_database()

    candidates = hybrid_search(
        db,
        query,
        requirements,
        top_k=5,
        category=category,
    )

    # Ask instead of guessing (task 1.1) -- and skip the 4-agent CrewAI
    # crew entirely when nothing in the catalog actually matched (task
    # 1.2's "use the crew well" cuts both ways: don't spend four agent
    # calls on a question that shouldn't be answered yet -- see
    # AGENTS/CLARIFICATION_AGENT.py). This is the deterministic,
    # no-LLM-call half of the old assess_clarity -- the customer-facing
    # sufficiency half already ran above, before hybrid_search.
    if check_clarity and retry_feedback is None:

        result_quality = assess_result_quality(candidates, product_noun, COMPANY_NAME)

        if result_quality["needs_clarification"]:

            return {
                "category": category,
                "text": result_quality["question"],
                "product": None,
                "candidates": candidates,
                "clarification": True,
            }

    rag_data = format_candidates_for_prompt(
        candidates
    )

    top_candidate_name = (
        candidates[0].get("name")
        if candidates
        else None
    )

    if top_candidate_name:

        user_request = (
            f'IMPORTANT: The scoring engine selected '
            f'"{top_candidate_name}" as the best matching '
            f'{product_noun}. Your first recommended product MUST '
            f'be this exact product.\n\n'
            + user_request
        )

    crew = _get_crew(category)

    result = crew.kickoff(
        inputs={
            "user_request": user_request,
            "rag_data": rag_data,
        }
    )

    text = _scrub_invented_purchase_prose(
        getattr(result, "raw", None)
        or str(result)
    )

    parsed_product_json = None

    tasks_output = getattr(
        result,
        "tasks_output",
        None,
    )

    if tasks_output:

        parsed_product_json = _extract_product_json(
            getattr(
                tasks_output[0],
                "raw",
                None,
            )
        )

    narratives = _narratives_from_parsed(
        parsed_product_json
    )

    top_picks = build_top_picks(
        candidates,
        narratives,
    )

    product = (
        {"top_picks": top_picks}
        if top_picks
        else None
    )

    usage = getattr(
        result,
        "token_usage",
        None,
    )

    if usage:
        logger.info(
            "%s crew token usage: %s",
            category,
            usage,
        )

    return {
        "category": category,
        "text": text,
        "product": product,
        "candidates": candidates,
        "clarification": False,
    }


def sales_agents(state: Graph_State):

    categories = state.get("categories", [])

    if not categories:

        return {
            "answer": DECLINE_MESSAGE,
            "context": "DENY",
            "product": None,
            "candidates": None,
        }

    requirements = extract_requirements(
        state["question"],
        _lobby_history_text(
            state.get("lobby"), categories
        ),
    )

    results = [
        _run_one_category(
            state,
            category,
            requirements,
        )
        for category in categories
    ]

    answer, product, candidates, all_clarification = _compose_results(
        results
    )

    return {
        "answer": answer,
        "product": product,
        "candidates": candidates,
        "requirements": requirements,
        "clarification": all_clarification,
    }


def exit_gaurd_agent(state: Graph_State):

    answer = state.get(
        "answer",
        DECLINE_MESSAGE,
    )

    update = {}

    context = state.get("context")

    # A clarifying question (whether from clarify_category, or every
    # category in sales_agents needing one) isn't a "sales answer" -- there
    # is nothing to fact-check it against, and running the evaluator on it
    # would just cost an LLM call for no benefit.
    skip_evaluation = (
        context in ("DENY", "GREETING", "CHAT", "CLARIFY_CATEGORY", "PRODUCT_FOLLOWUP")
        or bool(state.get("clarification"))
    )

    if skip_evaluation:

        update["evaluation"] = None
        update["retries"] = 0

    else:

        requirements = (
            state.get("requirements")
            or {}
        )

        candidates = state.get(
            "candidates"
        )

        evaluation = evaluate_response(
            state["question"],
            answer,
            _flatten_candidates(
                candidates
            ),
            requirements,
            min_score=getattr(
                config,
                "EVALUATION_MIN_SCORE",
                0.6,
            ),
        )

        retries = 0

        if not evaluation["passed"]:

            if getattr(
                config,
                "ENABLE_EVALUATOR_RETRY",
                True,
            ):

                retries = 1

                feedback = (
                    "; ".join(
                        evaluation.get("reasons")
                        or []
                    )
                    or "The response did not meet the quality bar."
                )

                categories = state.get(
                    "categories",
                    [],
                )

                retry_results = [
                    _run_one_category(
                        state,
                        category,
                        requirements,
                        retry_feedback=feedback,
                    )
                    for category in categories
                ]

                new_answer, new_product, new_candidates, _ = (
                    _compose_results(
                        retry_results
                    )
                )

                re_evaluation = evaluate_response(
                    state["question"],
                    new_answer,
                    _flatten_candidates(
                        new_candidates
                    ),
                    requirements,
                    min_score=getattr(
                        config,
                        "EVALUATION_MIN_SCORE",
                        0.6,
                    ),
                )

                if re_evaluation["passed"]:

                    answer = new_answer

                    update["product"] = (
                        new_product
                    )

                    update["candidates"] = (
                        new_candidates
                    )

                    evaluation = re_evaluation

                else:

                    answer = DECLINE_MESSAGE

                    update["context"] = "DENY"
                    update["product"] = None
                    update["candidates"] = None

                    evaluation = re_evaluation

            else:

                answer = DECLINE_MESSAGE

                update["context"] = "DENY"
                update["product"] = None
                update["candidates"] = None

        update["evaluation"] = evaluation
        update["retries"] = retries

    update["answer"] = answer

    update["history"] = [
        {
            "role": "assistant",
            "content": answer,
        }
    ]

    # File under whichever category(ies) actually produced this answer
    # (falls back to categories=[] -> "_general" for CHAT/GREETING/DENY/
    # CLARIFY_CATEGORY turns, same bucket the matching user turn went to
    # in entry_gaurd_agent above).
    update["lobby"] = _lobby_update(
        state.get("categories"),
        "assistant",
        answer,
    )

    return update


def get_graph():

    global _graph

    if _graph is not None:
        return _graph

    builder = StateGraph(
        Graph_State
    )

    builder.add_node(
        "entry_guard_agent",
        entry_gaurd_agent,
    )

    builder.add_node(
        "chatbot",
        chatbot,
    )

    builder.add_node(
        "greeting",
        greeting,
    )

    builder.add_node(
        "clarify_category",
        clarify_category,
    )

    builder.add_node(
        "sales_agents",
        sales_agents,
    )

    builder.add_node(
        "product_followup",
        product_followup,
    )

    builder.add_node(
        "exit_guard_agent",
        exit_gaurd_agent,
    )

    builder.add_edge(
        START,
        "entry_guard_agent",
    )

    builder.add_conditional_edges(
        "entry_guard_agent",
        router,
    )

    builder.add_edge(
        "chatbot",
        "exit_guard_agent",
    )

    builder.add_edge(
        "greeting",
        "exit_guard_agent",
    )

    builder.add_edge(
        "clarify_category",
        "exit_guard_agent",
    )

    builder.add_edge(
        "sales_agents",
        "exit_guard_agent",
    )

    builder.add_edge(
        "product_followup",
        "exit_guard_agent",
    )

    builder.add_edge(
        "exit_guard_agent",
        END,
    )

    _graph = builder.compile(
        checkpointer=_build_checkpointer()
    )

    return _graph


def _confidence_from(
    evaluation: Optional[dict],
    candidates: Optional[dict],
) -> Optional[float]:

    if (
        evaluation
        and evaluation.get("overall") is not None
    ):
        return evaluation["overall"]

    flat = _flatten_candidates(
        candidates
    )

    if flat:

        best = max(
            flat,
            key=lambda candidate: candidate.get(
                "_scores",
                {},
            ).get(
                "overall",
                0.0,
            ),
        )

        return best.get(
            "_scores",
            {},
        ).get(
            "overall"
        )

    return None


def _invoke(
    question: str,
    thread_id: str,
) -> dict:

    tracer = TraceBuilder(
        thread_id,
        question,
    )

    graph = get_graph()

    result = graph.invoke(
        {
            "question": question
        },
        config={
            "configurable": {
                "thread_id": thread_id
            }
        },
    )

    candidates = result.get(
        "candidates"
    )

    evaluation = result.get(
        "evaluation"
    )

    tracer.add(
        context=result.get(
            "context"
        ),
        categories=result.get(
            "categories"
        ),
        requirements=result.get(
            "requirements"
        ),
        candidates=candidates,
        evaluation=evaluation,
        retries=result.get(
            "retries",
            0,
        ),
    )

    tracer.finish()

    context = result.get(
        "context",
        "DENY",
    )

    product_data = result.get(
        "product"
    )

    if context == "RECOMMENDATION" and product_data:
        response_type = "recommendation"
    elif result.get("clarification") or context == "CLARIFY_CATEGORY":
        response_type = "clarification"
    else:
        response_type = "normal"

    return {
        "answer": result.get(
            "answer",
            DECLINE_MESSAGE,
        ),
        "context": context,
        "response_type": response_type,
        "product": product_data,
        "candidates": candidates,
        "confidence": _confidence_from(
            evaluation,
            candidates,
        ),
    }


def ask(
    question: str,
    thread_id: str = "default",
) -> dict:

    timeout = getattr(
        config,
        "REQUEST_TIMEOUT_SECONDS",
        90,
    )

    future = _executor.submit(
        _invoke,
        question,
        thread_id,
    )

    try:

        return future.result(
            timeout=timeout
        )

    except FutureTimeoutError:

        raise TimeoutError(
            f"Agent pipeline timed out after {timeout}s"
        ) from None


def get_history(
    thread_id: str,
) -> list:

    graph = get_graph()

    snapshot = graph.get_state(
        {
            "configurable": {
                "thread_id": thread_id
            }
        }
    )

    if not snapshot or not snapshot.values:
        return []

    return snapshot.values.get(
        "history",
        [],
    )


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    response = ask(
        "I want a good phone",
        "test-thread",
    )

    print(
        response["answer"]
    )
