import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app import __version__, company
from app.api.schemas import (
    THREAD_ID_PATTERN,
    CategorySummary,
    ChatRequest,
    ChatResponse,
    CompareRequest,
    HealthResponse,
    HistoryTurn,
)
from app.api.security import require_api_key
from app.catalog import database, tools
from app.core.config import get_settings
from app.services.chat import ChatService, ChatTimeout, ThreadBusy

logger = logging.getLogger("salesman.api")

router = APIRouter(prefix="/api")
protected = [Depends(require_api_key)]


def get_chat(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    settings = get_settings()
    checks = {"llm_configured": settings.llm_configured}
    try:
        database.check_connectivity()
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001
        checks["database"] = False
        logger.warning("Health check: database unreachable: %s", exc)
    ok = checks["llm_configured"] and checks["database"]
    return HealthResponse(status="ok" if ok else "degraded", version=__version__, checks=checks)


@router.get("/company", tags=["store"])
def get_company():
    return {**company.company_info(), "stores": company.list_stores()}


@router.get("/categories", response_model=list[CategorySummary], tags=["store"])
def categories():
    return database.category_overview()


@router.post("/chat", response_model=ChatResponse, dependencies=protected, tags=["chat"])
def chat(payload: ChatRequest, service: ChatService = Depends(get_chat)):
    thread_id = payload.thread_id or str(uuid.uuid4())
    try:
        return service.ask(payload.message, thread_id)
    except ChatTimeout as exc:
        raise HTTPException(status_code=504, detail="That took too long to answer. Please try again.") from exc
    except ThreadBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat turn failed (thread %s)", thread_id)
        raise HTTPException(status_code=500,
                            detail="Sorry, something went wrong while answering. Please try again.") from exc


@router.post("/chat/stream", dependencies=protected, tags=["chat"])
def chat_stream(payload: ChatRequest, service: ChatService = Depends(get_chat)):
    """Server-sent events: `status` while the assistant works, then one
    `final` (a ChatResponse) or `error`."""
    thread_id = payload.thread_id or str(uuid.uuid4())

    def events():
        yield _sse("start", {"thread_id": thread_id})
        for event in service.stream(payload.message, thread_id):
            kind = event.get("type", "status")
            if kind == "ping":
                yield ": ping\n\n"
            elif kind == "final":
                yield _sse("final", ChatResponse.model_validate(event["data"]).model_dump())
            else:
                yield _sse(kind, {k: v for k, v in event.items() if k != "type"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/threads/{thread_id}/history", response_model=list[HistoryTurn],
            dependencies=protected, tags=["chat"])
def history(thread_id: str, service: ChatService = Depends(get_chat)):
    _check_thread_id(thread_id)
    return service.history(thread_id)


@router.post("/compare", dependencies=protected, tags=["catalog"])
def compare(payload: CompareRequest):
    try:
        return tools.compare_products(payload.product_names, payload.category)
    except tools.ProductToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/products/search", dependencies=protected, tags=["catalog"])
def search(category: str | None = None, min_price: float | None = None,
           max_price: float | None = None, brand: str | None = None,
           q: str | None = None, limit: int = Query(20, ge=1, le=50)):
    try:
        return tools.search_products(category, min_price, max_price, brand, q, limit)
    except tools.ProductToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/traces", dependencies=protected, tags=["system"])
def traces(request: Request, thread_id: str | None = None, limit: int = Query(20, ge=1, le=100)):
    store = request.app.state.traces
    return store.list(thread_id, limit) if store else []


def _check_thread_id(thread_id: str) -> None:
    import re

    if not re.match(THREAD_ID_PATTERN, thread_id):
        raise HTTPException(status_code=422, detail="Invalid thread id")
