"""Test setup: isolated settings, no real LLM or database calls."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="salesman-tests-")
os.environ.update({
    "GOOGLE_API_KEY": "test-key",
    "DB_HOST": "localhost",
    "RATE_LIMIT_PER_MINUTE": "0",
    "CHROMA_DIR": os.path.join(_TMP, "chroma"),
    "CHECKPOINT_DB_PATH": os.path.join(_TMP, "checkpoints.sqlite"),
    "TRACE_DB_PATH": os.path.join(_TMP, "traces.sqlite"),
    "NORMALIZE_CATALOG_WITH_LLM": "false",
    "REQUEST_TIMEOUT_SECONDS": "10",
})

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.agents.advisor import AdvisorOutput  # noqa: E402
from app.agents.recommender import PickNote, RecommendationOutput  # noqa: E402
from app.agents.understanding import Understanding  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.graph.builder import build_graph  # noqa: E402
from app.graph.toolkit import Toolkit  # noqa: E402
from app.models import ShoppingProfile  # noqa: E402

PRODUCTS = [
    {"id": 1, "category": "Mobile", "name": "Galaxy M35 5G", "brand": "Samsung", "price": 21999, "mrp": 24999,
     "rating": 4.3, "units_available": 30, "offline_availability": "Available at Trein Koramangala",
     "online_link": "https://shop.example/m35", "description": "5G phone with AMOLED display",
     "ram": "8GB", "storage": "128GB", "battery": "6000mAh", "attribute_keys": ["ram", "storage", "battery"]},
    {"id": 2, "category": "Mobile", "name": "Redmi Note 14", "brand": "Xiaomi", "price": 18999, "mrp": 21999,
     "rating": 4.1, "units_available": 55, "offline_availability": "Available at Trein T Nagar",
     "description": "Fast charging and a sharp AMOLED screen",
     "ram": "8GB", "storage": "256GB", "battery": "5500mAh", "attribute_keys": ["ram", "storage", "battery"]},
    {"id": 3, "category": "Mobile", "name": "iPhone 15", "brand": "Apple", "price": 69999, "mrp": 79900,
     "rating": 4.7, "units_available": 0, "offline_availability": "Available at Trein T Nagar, Banjara Hills",
     "description": "A16 Bionic, 48MP camera", "ram": "6GB", "storage": "128GB", "battery": "3349mAh",
     "attribute_keys": ["ram", "storage", "battery"]},
    {"id": 4, "category": "Laptop", "name": "ThinkPad E14", "brand": "Lenovo", "price": 65999, "rating": 4.4,
     "units_available": 12, "ram": "16GB", "storage": "512GB SSD", "processor": "Ryzen 7",
     "attribute_keys": ["ram", "storage", "processor"]},
]

OVERVIEW = [
    {"name": "Laptop", "product_count": 1, "min_price": 65999, "max_price": 65999, "brands": ["Lenovo"]},
    {"name": "Mobile", "product_count": 3, "min_price": 18999, "max_price": 69999,
     "brands": ["Apple", "Samsung", "Xiaomi"]},
]


def semantic_search(query, category, k):
    rows = [p for p in PRODUCTS if not category or p["category"] == category]
    return [(dict(p), 0.9 - i * 0.1) for i, p in enumerate(rows)][:k]


def understanding(action="recommend", reply="", referenced=None, suggestions=None, **profile):
    profile.setdefault("categories", ["Mobile"])
    return Understanding(action=action, reply=reply, profile=ShoppingProfile(**profile),
                         referenced_products=referenced or [], suggestions=suggestions or ["Under ₹30,000"])


class FakeAgents:
    """Scriptable stand-ins for the three LLM agents; records calls."""

    def __init__(self):
        self.next_understanding = understanding()
        self.recommend_picks = ["Redmi Note 14", "Galaxy M35 5G"]
        self.advice = AdvisorOutput(message="The Redmi has more storage.", compare_products=[], show_products=[])
        self.fail = set()
        self.calls = {"understand": [], "recommend": [], "advise": []}

    def understand(self, variables):
        self.calls["understand"].append(variables)
        if "understand" in self.fail:
            raise RuntimeError("llm down")
        return self.next_understanding

    def recommend(self, variables):
        self.calls["recommend"].append(variables)
        if "recommend" in self.fail:
            raise RuntimeError("llm down")
        return RecommendationOutput(
            message="The **Redmi Note 14** is your best bet.",
            picks=[PickNote(name=n, headline=f"{n} headline", why="Great value", key_features=["AMOLED"])
                   for n in self.recommend_picks],
            suggestions=["Compare the top two"],
        )

    def advise(self, variables):
        self.calls["advise"].append(variables)
        if "advise" in self.fail:
            raise RuntimeError("llm down")
        return self.advice


@pytest.fixture
def agents():
    return FakeAgents()


@pytest.fixture
def toolkit(agents):
    return Toolkit(
        understand=agents.understand,
        recommend=agents.recommend,
        advise=agents.advise,
        semantic_search=semantic_search,
        fallback_rows=lambda category: [dict(p) for p in PRODUCTS if not category or p["category"] == category],
        lookup_products=lambda names: [dict(p) for p in PRODUCTS if p["name"] in names],
        catalog_overview=lambda: OVERVIEW,
    )


@pytest.fixture
def graph(toolkit):
    return build_graph(toolkit, get_settings(), InMemorySaver())


@pytest.fixture
def run(graph):
    """run(message, thread="t1") -> final state values."""
    def _run(message, thread="t1"):
        config = {"configurable": {"thread_id": thread}}
        graph.invoke({"message": message}, config)
        return graph.get_state(config).values
    return _run
