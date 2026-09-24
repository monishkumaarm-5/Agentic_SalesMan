import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window limiter, keyed by client IP, applied
    only to /api/* paths.

    Each chat message triggers several LLM calls (a 4-agent CrewAI crew per
    matched category), so this doubles as basic cost protection, not just
    abuse prevention. Good enough for a single-process deployment; swap for
    a shared store (e.g. Redis) if this ever runs as multiple processes or
    instances behind a load balancer, since each process would otherwise
    track its own separate counts.
    """

    # Liveness probes (load balancers, Docker healthchecks) poll this
    # constantly and must never be throttled into looking "down".
    EXEMPT_PATHS = frozenset({"/api/health"})
    # How many distinct clients to track before sweeping out idle ones.
    PRUNE_THRESHOLD = 500

    def __init__(self, app, requests_per_minute: int = 20, window_seconds: float = 60.0):
        super().__init__(app)
        self.limit = requests_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        """Drops clients whose most recent hit has aged out of the window.
        (Checking only for already-empty deques never freed anything: a
        client's deque is only trimmed when that same client returns.)"""
        stale = [ip for ip, q in self._hits.items() if not q or now - q[-1] > self.window]
        for ip in stale:
            del self._hits[ip]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.limit <= 0 or not path.startswith("/api/") or path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            hits = self._hits[client_ip]
            while hits and now - hits[0] > self.window:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = max(0.0, self.window - (now - hits[0]))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded, please slow down."},
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )

            hits.append(now)

            # Keep memory bounded as new clients come and go.
            if len(self._hits) > self.PRUNE_THRESHOLD:
                self._prune(now)

        return await call_next(request)
