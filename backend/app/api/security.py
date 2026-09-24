import hmac
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Header, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """No-op unless API_KEY is set; then X-API-Key must match (constant time)."""
    settings = get_settings()
    if not settings.auth_enabled:
        return
    expected = settings.api_key.strip().encode()
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window per client IP on /api/*. Per-process only:
    use a shared store (e.g. Redis) when running several workers."""

    EXEMPT_PATHS = frozenset({"/api/health"})
    PRUNE_THRESHOLD = 1000

    def __init__(self, app, requests_per_minute: int = 30, window_seconds: float = 60.0):
        super().__init__(app)
        self.limit = requests_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        for ip in [ip for ip, q in self._hits.items() if not q or now - q[-1] > self.window]:
            del self._hits[ip]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.limit <= 0 or not path.startswith("/api/") or path in self.EXEMPT_PATHS:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            hits = self._hits[ip]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = int(max(0.0, self.window - (now - hits[0]))) + 1
                return JSONResponse(status_code=429, headers={"Retry-After": str(retry)},
                                    content={"detail": "You're sending messages too quickly -- please wait a moment."})
            hits.append(now)
            if len(self._hits) > self.PRUNE_THRESHOLD:
                self._prune(now)
        return await call_next(request)
