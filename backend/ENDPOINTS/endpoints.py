import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import config
from APP.auth import require_api_key
from DATABASE.SQL_CONNECTOR import check_mysql_connectivity, list_categories
from TOOLS.company_tools import get_company_info, list_store_locations
from TOOLS.product_tools import ProductToolError, compare_products
from WORKFLOW.ORCHE import ask, get_history
from WORKFLOW.tracing import get_traces

logger = logging.getLogger("agentic_salesman.api")

router = APIRouter(prefix="/api", tags=["sales-agent"])

# Applied per-route (not at the router level) so /api/health stays reachable
# without a key even when API_KEY is configured -- load balancers, Docker
# healthchecks and uptime monitors shouldn't need a secret to ask "are you
# up?".
auth_dep = Depends(require_api_key)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000, description="Customer's message")
    thread_id: Optional[str] = Field(
        default=None,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description=(
            "Conversation id used to keep chat history/context between "
            "calls. A new one is generated and returned if omitted."
        ),
    )


class ChatResponse(BaseModel):
    answer: str
    context: str
    thread_id: str
    response_type: str = Field(
        default="normal",
        description=(
            "'normal' for conversational answers (greetings, general "
            "questions, declines); 'recommendation' when the response "
            "contains product recommendation cards in the `product` "
            "field; 'clarification' when the assistant is asking the "
            "customer a follow-up question instead of recommending "
            "something -- either because the category itself was unclear, "
            "or because the catalog/requirements were too thin to "
            "recommend responsibly (see AGENTS/CLARIFICATION_AGENT.py). "
            "The frontend uses this flag to decide whether to render a "
            "plain chat bubble or the product-detail panel."
        ),
    )
    product: Optional[dict] = Field(
        default=None,
        description=(
            "`{\"top_picks\": [...]}` -- up to 3 ranked recommendation "
            "cards built by WORKFLOW/recommendations.py from the same "
            "scored candidates as `candidates` below. Each entry: "
            "{rank, name, specs, scores, buy, why_this, key_features, "
            "why_suits_you}. `specs`/`scores`/`buy` are deterministic, "
            "straight from the catalog (never invented); `buy` carries "
            "price/currency plus mrp/discount_percentage/units_available/"
            "in_stock/online_link/offline_availability, each null when the "
            "catalog doesn't track that column. `why_this`/`key_features`/"
            "`why_suits_you` are the product agent's own narrative for "
            "that specific product, matched back onto it by name. For a "
            "multi-category answer this is a dict keyed by category "
            "(e.g. {\"LAPTOP\": {\"top_picks\": [...]}}) instead of a "
            "single top_picks list."
        ),
    )
    candidates: Optional[dict] = Field(
        default=None,
        description=(
            "The scored shortlist hybrid retrieval considered for this "
            "answer (see WORKFLOW/retrieval.py + WORKFLOW/scoring.py), "
            "keyed by category. Each candidate carries a '_scores' "
            "breakdown (semantic/budget_fit/spec_match/rating/brand_fit -> "
            "overall) explaining why it ranked where it did."
        ),
    )
    confidence: Optional[float] = Field(
        default=None,
        description=(
            "0-1 confidence in this answer: the exit evaluator's overall "
            "score when available, otherwise the best candidate's overall "
            "retrieval score. null for greetings/declines, which aren't "
            "evaluated."
        ),
    )


class HistoryTurn(BaseModel):
    role: str
    content: str


class HealthResponse(BaseModel):
    status: str
    checks: dict


class CompareRequest(BaseModel):
    category: str = Field(
        ...,
        description=(
            "Any category this store's catalog currently has (see GET "
            "/api/categories for the live list) -- e.g. 'Mobile', "
            "'Laptop', 'Refrigerator'."
        ),
    )
    product_names: list[str] = Field(
        ..., min_length=2, max_length=10, description="2-10 exact product names"
    )


class CompareResponse(BaseModel):
    category: str
    products: dict
    differing_fields: list[str]
    missing: list[str]


@router.get("/health", response_model=HealthResponse)
def health():
    """Lightweight readiness check -- never raises. Reports whether the
    required config looks filled in and, cheaply, whether MySQL is
    reachable. Does not call the LLM (too slow/expensive to do on every
    health check)."""
    checks = {}

    google_key = getattr(config, "GOOGLE_API_KEY", "") or ""
    checks["google_api_key_configured"] = bool(
        google_key and google_key != "your-google-api-key-here"
    )

    db_password = getattr(config, "DB_PASSWORD", "") or ""
    checks["db_credentials_configured"] = bool(
        db_password and db_password != "your-db-password"
    )

    try:
        check_mysql_connectivity()
        checks["database_reachable"] = True
    except Exception as exc:
        checks["database_reachable"] = False
        checks["database_error"] = str(exc)

    critical = ("google_api_key_configured", "db_credentials_configured", "database_reachable")
    overall = "ok" if all(checks.get(c) for c in critical) else "degraded"
    return HealthResponse(status=overall, checks=checks)


@router.get("/company")
def company():
    """Company identity + physical store locations (task 1.3: this is a
    company-specific app -- the assistant's own store locations and
    website need to be discoverable on their own, not just mentioned in
    passing inside a chat answer). Reads straight from
    TOOLS/company_tools.py, which in turn reads config.py's
    COMPANY_NAME/COMPANY_WEBSITE/STORE_LOCATIONS -- no auth required, same
    reasoning as /api/health (this is public storefront information, not a
    secret)."""
    info = get_company_info()
    info["stores"] = list_store_locations()
    return info


@router.get("/categories")
def categories():
    """Live list of product categories this store's catalog currently has
    (see DATABASE/SQL_CONNECTOR.py) -- lets the frontend show real
    category suggestions/examples instead of a hardcoded phone/laptop/
    headphone list. No auth required, same reasoning as /api/company."""
    return {"categories": list_categories()}


@router.post("/chat", response_model=ChatResponse, dependencies=[auth_dep])
def chat(payload: ChatRequest):
    thread_id = payload.thread_id or str(uuid.uuid4())
    logger.info(
        "POST /api/chat thread_id=%s question=%r",
        thread_id,
        payload.question[:200],
    )
    try:
        result = ask(payload.question, thread_id=thread_id)
    except TimeoutError as exc:
        logger.warning("Timeout in /api/chat thread_id=%s: %s", thread_id, exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        # Log the details, but don't echo raw exception text (SQL errors,
        # file paths, upstream API messages) back to the browser.
        logger.exception("Unhandled error in /api/chat thread_id=%s", thread_id)
        raise HTTPException(
            status_code=500,
            detail="Sorry, something went wrong while answering. Please try again.",
        ) from exc

    response = ChatResponse(
        answer=result["answer"],
        context=result["context"],
        thread_id=thread_id,
        response_type=result.get("response_type", "normal"),
        product=result.get("product"),
        candidates=result.get("candidates"),
        confidence=result.get("confidence"),
    )
    logger.info(
        "POST /api/chat thread_id=%s response_type=%s confidence=%s "
        "answer_len=%d has_product=%s has_candidates=%s",
        thread_id,
        response.response_type,
        response.confidence,
        len(response.answer or ""),
        response.product is not None,
        response.candidates is not None,
    )
    return response


@router.get("/history/{thread_id}", response_model=list[HistoryTurn], dependencies=[auth_dep])
def history(thread_id: str):
    return get_history(thread_id)


@router.post("/compare", response_model=CompareResponse, dependencies=[auth_dep])
def compare(payload: CompareRequest):
    """Deterministic, LLM-free product comparison -- reads straight from
    MySQL via TOOLS/product_tools.py (the same function the CrewAI product
    agent and the standalone MCP server both call). Useful on its own (fast,
    no token cost) and as the backing for a "Compare" UI action."""
    logger.info(
        "POST /api/compare category=%s product_names=%s",
        payload.category,
        payload.product_names,
    )
    try:
        result = compare_products(payload.category, payload.product_names)
    except ProductToolError as exc:
        logger.warning("Bad request in /api/compare: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/compare")
        raise HTTPException(
            status_code=500, detail="Could not compare these products right now."
        ) from exc

    logger.info(
        "POST /api/compare category=%s differing_fields=%s missing=%s",
        payload.category,
        result.get("differing_fields"),
        result.get("missing"),
    )
    return result


@router.get("/traces", dependencies=[auth_dep])
def traces(thread_id: Optional[str] = None, limit: int = 20):
    """Execution trace log (WORKFLOW/tracing.py) -- routing, retrieval
    candidates/scores, evaluator scores, retries and latency per chat turn.
    Returned as loosely-typed JSON (not a strict response_model) since the
    trace payload's shape can evolve without bumping the chat API."""
    return get_traces(thread_id=thread_id, limit=min(max(limit, 1), 100))
