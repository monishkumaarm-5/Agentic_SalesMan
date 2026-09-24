import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from APP.rate_limit import RateLimitMiddleware
from ENDPOINTS.endpoints import router as api_router

logging.basicConfig(
    level=getattr(logging, str(getattr(config, "LOG_LEVEL", "INFO")).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agentic_salesman.app")

allowed_origins = [
    origin.strip()
    for origin in getattr(config, "ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    api_key_set = bool((getattr(config, "API_KEY", "") or "").strip())

    logger.info("=" * 60)
    logger.info("  Agentic SalesMan API starting up")
    logger.info("=" * 60)
    logger.info("CORS allowed origins: %s", allowed_origins)
    logger.info("API key auth: %s", "enabled" if api_key_set else "disabled (open API)")
    logger.info("Rate limit: %s req/min per IP", getattr(config, "RATE_LIMIT_PER_MINUTE", 20))
    logger.info("Request timeout: %ss", getattr(config, "REQUEST_TIMEOUT_SECONDS", 60))
    logger.info("Evaluator min score: %s", getattr(config, "EVALUATION_MIN_SCORE", 0.6))
    logger.info("Evaluator retry: %s", getattr(config, "ENABLE_EVALUATOR_RETRY", True))

    # Pre-flight DB check (non-blocking — just warn if DB is unreachable)
    try:
        from DATABASE.SQL_CONNECTOR import check_mysql_connectivity
        check_mysql_connectivity(timeout_seconds=5)
        logger.info("MySQL connection: OK")
    except Exception as exc:
        logger.warning("MySQL connection: FAILED — %s", exc)
        logger.warning("The API will start but /api/chat will fail until the DB is reachable.")

    google_key = getattr(config, "GOOGLE_API_KEY", "") or ""
    if not google_key or google_key == "your-google-api-key-here":
        logger.warning("GOOGLE_API_KEY is not set — LLM calls will fail.")

    logger.info("Startup complete — listening for requests")
    yield
    logger.info("Agentic SalesMan API shutting down")


_company_name = getattr(config, "COMPANY_NAME", "Trein")

app = FastAPI(
    title=f"{_company_name} Shopping Assistant API",
    description=(
        f"Multi-agent, multi-category sales assistant for {_company_name} "
        f"— powered by the Agentic SalesMan pipeline (LangGraph + CrewAI)."
    ),
    version="2.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=getattr(config, "RATE_LIMIT_PER_MINUTE", 20),
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """Log request duration for /api/* routes."""
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "%s %s → %d (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Response-Time"] = f"{elapsed_ms:.0f}ms"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions so they return JSON, not HTML."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": f"{_company_name} Shopping Assistant API",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
