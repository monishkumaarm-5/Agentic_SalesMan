"""FastAPI application factory.

    uvicorn app.main:app --reload
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router
from app.api.security import RateLimitMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.chat import ChatService
from app.services.tracing import TraceStore

logger = logging.getLogger("salesman.app")


def _default_service(traces: TraceStore) -> ChatService:
    from app.graph.builder import build_graph
    from app.graph.toolkit import default_toolkit

    settings = get_settings()
    return ChatService(build_graph(default_toolkit(), settings), settings, traces)


def create_app(service: ChatService | None = None, traces: TraceStore | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.traces = traces if traces is not None else TraceStore(settings.trace_db_path)
        app.state.chat_service = service or _default_service(app.state.traces)
        if service is None and settings.warm_index_on_startup:
            from app.graph.toolkit import warm_index

            warm_index()  # background thread; chats use DB search until ready
        logger.info("%s assistant API v%s ready (model %s, auth %s, rate limit %s/min)",
                    settings.company_name, __version__, settings.llm_model,
                    "on" if settings.auth_enabled else "off", settings.rate_limit_per_minute)
        if not settings.llm_configured:
            logger.warning("GOOGLE_API_KEY is not set -- the assistant cannot answer chats.")
        yield

    app = FastAPI(
        title=f"{settings.company_name} Shopping Assistant API",
        description="Multi-agent shopping assistant: LangGraph workflow, Gemini agents, hybrid catalog search.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/"):
            logger.info("%s %s -> %d (%.0fms) [%s]", request.method, request.url.path,
                        response.status_code, elapsed, request_id)
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "An internal error occurred. Please try again."})

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": app.title, "version": __version__, "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
