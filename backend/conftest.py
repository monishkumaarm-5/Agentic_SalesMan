"""
Session-wide test setup (pytest auto-discovers a root conftest.py before
collecting any test module).

The AGENTS modules build their Gemini client as soon as they're imported,
which requires GOOGLE_API_KEY to already be set -- tests never make real
API/DB calls (everything is mocked), so placeholder values are enough. This
also creates a throwaway config.py from config.dummy.py if one doesn't
already exist, so `pytest` works out of the box in CI / a fresh clone
without needing real secrets.
"""
import os
import shutil

_ROOT = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(_ROOT, "config.py")
_dummy_path = os.path.join(_ROOT, "config.dummy.py")

os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder-key")
os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault(
    "CHECKPOINT_DB_PATH", "/tmp/agentic_salesman_test_checkpoints.sqlite"
)
os.environ.setdefault("TRACE_DB_PATH", "/tmp/agentic_salesman_test_traces.sqlite")
# The app-wide rate limiter would otherwise start returning 429 partway
# through the API test module (tests/test_rate_limit.py exercises the
# middleware on its own app instance).
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

if not os.path.exists(_config_path) and os.path.exists(_dummy_path):
    shutil.copy(_dummy_path, _config_path)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_shared_db_engine():
    """DATABASE.SQL_CONNECTOR caches one pooled engine per process; reset it
    around every test so a mocked engine never leaks into the next test."""
    from DATABASE import SQL_CONNECTOR

    SQL_CONNECTOR._shared_engine = None
    yield
    SQL_CONNECTOR._shared_engine = None
