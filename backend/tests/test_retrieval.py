"""Tests for WORKFLOW/retrieval.py's hybrid search."""
from WORKFLOW.retrieval import format_candidates_for_prompt, hybrid_search


class FakeDoc:
    def __init__(self, metadata, content=""):
        self.metadata = metadata
        self.page_content = content


class RelevanceScoreStore:
    """Implements similarity_search_with_relevance_scores -- the preferred
    API path."""

    def __init__(self, hits):
        self._hits = hits

    def similarity_search_with_relevance_scores(self, query, k=4, **kwargs):
        return self._hits[:k]


class DistanceScoreStore:
    """Only implements similarity_search_with_score (raw distances, lower
    is better) -- exercises the fallback normalization path."""

    def __init__(self, hits):
        self._hits = hits  # list of (doc, distance)

    def similarity_search_with_relevance_scores(self, query, k=4, **kwargs):
        raise NotImplementedError("this store doesn't support relevance scores")

    def similarity_search_with_score(self, query, k=4, **kwargs):
        return self._hits[:k]


class PlainSearchStore:
    """Only implements the plainest similarity_search -- exercises the
    rank-based fallback."""

    def __init__(self, docs):
        self._docs = docs

    def similarity_search_with_relevance_scores(self, query, k=4, **kwargs):
        raise NotImplementedError

    def similarity_search_with_score(self, query, k=4, **kwargs):
        raise NotImplementedError

    def similarity_search(self, query, k=4, **kwargs):
        return self._docs[:k]


def test_hybrid_search_uses_relevance_scores_when_available():
    store = RelevanceScoreStore(
        [
            (FakeDoc({"name": "Lenovo LOQ", "brand": "Lenovo", "ram": "16GB", "price": 72999}), 0.9),
            (FakeDoc({"name": "HP Pavilion", "brand": "HP", "ram": "8GB", "price": 55000}), 0.6),
        ]
    )
    candidates = hybrid_search(store, "laptop for coding", {}, top_k=2)
    assert [c["name"] for c in candidates] == ["Lenovo LOQ", "HP Pavilion"]
    assert all("_scores" in c for c in candidates)


def test_hybrid_search_falls_back_to_distance_scores():
    store = DistanceScoreStore(
        [
            (FakeDoc({"name": "Close Match", "price": 1000}), 0.1),  # small distance = close
            (FakeDoc({"name": "Far Match", "price": 1000}), 0.9),
        ]
    )
    candidates = hybrid_search(store, "query", {}, top_k=2)
    names = [c["name"] for c in candidates]
    assert names[0] == "Close Match"  # lower distance -> higher relevance -> ranked first


def test_hybrid_search_falls_back_to_plain_search_with_rank_scores():
    store = PlainSearchStore(
        [
            FakeDoc({"name": "First", "price": 1000}),
            FakeDoc({"name": "Second", "price": 1000}),
        ]
    )
    candidates = hybrid_search(store, "query", {}, top_k=2)
    assert [c["name"] for c in candidates] == ["First", "Second"]


def test_hybrid_search_reranks_by_requirements_not_just_semantic_order():
    # Dell XPS is the top semantic hit but way over budget; Lenovo LOQ is
    # #2 semantically but fits the budget -- scoring should promote it.
    store = RelevanceScoreStore(
        [
            (FakeDoc({"name": "Dell XPS", "brand": "Dell", "ram": "32GB", "price": 150000}), 0.95),
            (FakeDoc({"name": "Lenovo LOQ", "brand": "Lenovo", "ram": "16GB", "price": 72999}), 0.7),
        ]
    )
    requirements = {"budget_max": 80000, "use_cases": [], "brand": None}
    candidates = hybrid_search(store, "laptop", requirements, top_k=2)
    assert candidates[0]["name"] == "Lenovo LOQ"


def test_hybrid_search_deduplicates_by_name():
    store = RelevanceScoreStore(
        [
            (FakeDoc({"name": "Lenovo LOQ", "price": 72999}), 0.9),
            (FakeDoc({"name": "Lenovo LOQ", "price": 72999}), 0.8),
        ]
    )
    candidates = hybrid_search(store, "laptop", {}, top_k=5)
    assert len(candidates) == 1


def test_hybrid_search_returns_empty_list_for_no_hits():
    store = RelevanceScoreStore([])
    assert hybrid_search(store, "laptop", {}, top_k=5) == []


def test_format_candidates_for_prompt_handles_empty_list():
    assert "No matching products" in format_candidates_for_prompt([])


def test_format_candidates_for_prompt_includes_scores():
    candidates = [{"name": "X", "price": 100, "_scores": {"overall": 0.87}}]
    text = format_candidates_for_prompt(candidates)
    assert "X" in text
    assert "0.87" in text
