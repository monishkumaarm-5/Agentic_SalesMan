import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    logger.info("Agentic SalesMan API starting up")
    logger.info("CORS allowed origins: %s", allowed_origins)
    logger.info("API key auth: %s", "enabled" if api_key_set else "disabled (open API)")
    logger.info("Rate limit: %s requests/minute per IP", getattr(config, "RATE_LIMIT_PER_MINUTE", 20))
    logger.info("Request timeout: %ss", getattr(config, "REQUEST_TIMEOUT_SECONDS", 60))
    yield


app = FastAPI(
    title="Agentic SalesMan API",
    description="Multi-agent sales assistant for phones, laptops and headphones.",
    version="1.1.0",
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

app.include_router(api_router)


@app.get("/")
def root():
    return {"message": "Agentic SalesMan API is running. See /docs for the API reference."}
