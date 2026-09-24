"""
Everything the workflow nodes call out to, bundled so tests (and
alternative deployments) can swap any piece without monkeypatching.
"""
import logging
import threading
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


class _LazyIndex:
    """Builds and syncs the catalog index on first use, once."""

    def __init__(self):
        self._index = None
        self._lock = threading.Lock()

    def get(self):
        if self._index is None:
            with self._lock:
                if self._index is None:
                    from app.catalog.index import CatalogIndex

                    index = CatalogIndex()
                    index.sync()
                    self._index = index
        return self._index


_lazy_index = _LazyIndex()


def get_index():
    return _lazy_index.get()


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
