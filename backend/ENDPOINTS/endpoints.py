import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import config
from APP.auth import require_api_key
from DATABASE.SQL_CONNECTOR import check_mysql_connectivity
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
    question: str = Field(..., min_length=1, description="Customer's message")
    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation id used to keep chat history/context between "
            "calls. A new one is generated and returned if omitted."
        ),
    )


class ChatResponse(BaseModel):
    answer: str
    context: str
    thread_id: str
    product: Optional[dict] = Field(
        default=None,
        description=(
            "Structured product data (recommended_product, reason, "
            "key_features, buy_link) extracted from the product agent's "
            "output when available. For a multi-category answer this is a "
            "dict keyed by category instead of a single product."
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
    category: str = Field(..., description="'phone', 'laptop' or 'headphone'")
    product_names: list[str] = Field(..., min_length=2, description="2+ exact product names")


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


@router.post("/chat", response_model=ChatResponse, dependencies=[auth_dep])
def chat(payload: ChatRequest):
    thread_id = payload.thread_id or str(uuid.uuid4())
    try:
        result = ask(payload.question, thread_id=thread_id)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/chat")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result["answer"],
        context=result["context"],
        thread_id=thread_id,
        product=result.get("product"),
        candidates=result.get("candidates"),
        confidence=result.get("confidence"),
    )


@router.get("/history/{thread_id}", response_model=list[HistoryTurn], dependencies=[auth_dep])
def history(thread_id: str):
    return get_history(thread_id)


@router.post("/compare", response_model=CompareResponse, dependencies=[auth_dep])
def compare(payload: CompareRequest):
    """Deterministic, LLM-free product comparison -- reads straight from
    MySQL via TOOLS/product_tools.py (the same function the CrewAI product
    agent and the standalone MCP server both call). Useful on its own (fast,
    no token cost) and as the backing for a "Compare" UI action."""
    try:
        return compare_products(payload.category, payload.product_names)
    except ProductToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/compare")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/traces", dependencies=[auth_dep])
def traces(thread_id: Optional[str] = None, limit: int = 20):
    """Execution trace log (WORKFLOW/tracing.py) -- routing, retrieval
    candidates/scores, evaluator scores, retries and latency per chat turn.
    Returned as loosely-typed JSON (not a strict response_model) since the
    trace payload's shape can evolve without bumping the chat API."""
    return get_traces(thread_id=thread_id, limit=min(max(limit, 1), 100))
