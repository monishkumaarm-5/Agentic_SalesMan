import hmac
import logging

from fastapi import Header, HTTPException, status

import config

logger = logging.getLogger("agentic_salesman.auth")

_warned_unauthenticated = False


def _auth_enabled() -> bool:
    return bool((getattr(config, "API_KEY", "") or "").strip())


async def require_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    """FastAPI dependency guarding /api/* routes.

    No-op when config.API_KEY is unset -- that's the default, so a fresh
    checkout keeps working with zero setup. Set API_KEY (in config.py or as
    an env var) before exposing this API to anything beyond your own
    machine; once set, every request must send it back as X-API-Key.
    """
    global _warned_unauthenticated
    if not _auth_enabled():
        if not _warned_unauthenticated:
            logger.warning(
                "API_KEY is not set -- the API is unauthenticated. Set "
                "API_KEY (config.py or the API_KEY env var) before exposing "
                "this beyond your own machine."
            )
            _warned_unauthenticated = True
        return

    expected = str(config.API_KEY).strip()
    # Constant-time comparison so the key can't be recovered by timing.
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
