"""
Everything the workflow nodes call out to, bundled so tests (and
alternative deployments) can swap any piece without monkeypatching.
"""
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.agents.advisor import AdvisorOutput
from app.agents.recommender import RecommendationOutput
from app.agents.understanding import Understanding

logger = logging.getLogger("salesman.toolkit")


@dataclass
class Toolkit:
    understand: Callable[[dict], Understanding]
    recommend: Callable[[dict], RecommendationOutput]
    advise: Callable[[dict], AdvisorOutput]
    semantic_search: Callable[[str, str | None, int], list]
    fallback_rows: Callable[[str | None], list]
    lookup_products: Callable[[list], list]
    catalog_overview: Callable[[], list]


class IndexNotReady(RuntimeError):
    """The semantic index is still being built; callers fall back to
    scoring catalog rows straight from MySQL."""


class _BackgroundIndex:
    """Builds and syncs the catalog index on a background thread.

    Building can take minutes the first time (embedding-model download,
    embedding every product, optional LLM spec filling), so it must never
    run inside a chat request: until it's ready, `get()` raises
    IndexNotReady and search falls back to the database."""

    RETRY_AFTER_SECONDS = 60

    def __init__(self):
        self._index = None
        self._lock = threading.Lock()
        self._state = "idle"          # idle | building | ready | failed
        self._failed_at = 0.0
        self._error: str | None = None

    @property
    def status(self) -> dict:
        return {"state": self._state, "error": self._error}

    def warm(self) -> None:
        with self._lock:
            if self._state in ("building", "ready"):
                return
            if self._state == "failed" and time.monotonic() - self._failed_at < self.RETRY_AFTER_SECONDS:
                return
            self._state = "building"
        threading.Thread(target=self._build, name="catalog-index", daemon=True).start()

    def _build(self) -> None:
        started = time.monotonic()
        logger.info("Catalog index: build started in the background")
        try:
            from app.catalog.index import CatalogIndex

            index = CatalogIndex()
            report = index.sync()
            self._index, self._state, self._error = index, "ready", None
            logger.info("Catalog index: ready in %.1fs (%d products, rebuilt=%s, partial=%d, rejected=%d)",
                        time.monotonic() - started, report.indexed, report.rebuilt,
                        len(report.partial), len(report.rejected))
        except Exception as exc:  # noqa: BLE001
            self._state, self._failed_at, self._error = "failed", time.monotonic(), str(exc)
            logger.exception("Catalog index: build failed after %.1fs -- chats will use "
                             "database search until it succeeds", time.monotonic() - started)

    def get(self):
        if self._state == "ready":
            return self._index
        self.warm()
        raise IndexNotReady(f"catalog index is {self._state}")


_index = _BackgroundIndex()


def get_index():
    return _index.get()


def warm_index() -> None:
    _index.warm()


def index_status() -> dict:
    return _index.status


def default_toolkit() -> Toolkit:
    from app.agents.advisor import advise
    from app.agents.recommender import recommend
    from app.agents.understanding import understand
    from app.catalog import tools
    from app.catalog.database import category_overview, load_raw_products
    from app.catalog.index import rows_from_dataframe

    return Toolkit(
        understand=understand,
        recommend=recommend,
        advise=advise,
        semantic_search=lambda query, category, k: get_index().search(query, category, k),
        fallback_rows=lambda category: rows_from_dataframe(load_raw_products(category)),
        lookup_products=lambda names: tools.find_products(names),
        catalog_overview=category_overview,
    )
