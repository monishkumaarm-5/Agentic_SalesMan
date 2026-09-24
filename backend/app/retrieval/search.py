"""
Hybrid retrieval: semantic search over the catalog index, re-ranked by
the explainable scoring in app.retrieval.scoring.
"""
import logging
from collections.abc import Callable, Iterable

from app.models import ShoppingProfile
from app.retrieval.scoring import keyword_relevance, score_product

logger = logging.getLogger("salesman.retrieval")

# Fetch more than we return so scoring has room to re-rank.
FETCH_MULTIPLIER = 4

SemanticSearch = Callable[[str, str | None, int], list]  # -> [(row, relevance)]
FallbackRows = Callable[[str | None], list]              # -> [row]


def build_query(message: str, profile: ShoppingProfile, category: str | None) -> str:
    parts = [category or "", *profile.use_cases, *profile.must_haves, *profile.preferred_brands, message]
    return " ".join(p for p in parts if p).strip()


def hybrid_search(
    semantic: SemanticSearch,
    message: str,
    profile: ShoppingProfile,
    category: str | None,
    top_k: int = 6,
    exclude_names: Iterable[str] = (),
    fallback: FallbackRows | None = None,
) -> list[dict]:
    """Up to `top_k` products for one category, each with a `_scores`
    breakdown, best first."""
    excluded = {n.strip().lower() for n in exclude_names if n}
    query = build_query(message, profile, category)

    try:
        hits = semantic(query, category, max(top_k * FETCH_MULTIPLIER, 20))
    except Exception as exc:  # noqa: BLE001
        if fallback is None:
            raise
        logger.warning("Semantic search unavailable (%s); ranking catalog rows by keyword overlap", exc)
        hits = [(row, keyword_relevance(query, row)) for row in fallback(category)]

    avoid = {b.lower() for b in profile.avoid_brands}
    candidates, seen = [], set()
    for row, relevance in hits:
        name = str(row.get("name") or "").strip()
        key = name.lower()
        if not name or key in seen or key in excluded:
            continue
        seen.add(key)
        candidates.append({**row, "_scores": score_product(row, profile, relevance)})

    # Drop avoided brands unless that would leave nothing to show.
    preferred = [c for c in candidates if str(c.get("brand") or "").lower() not in avoid]
    candidates = preferred or candidates

    candidates.sort(key=lambda c: c["_scores"]["overall"], reverse=True)
    return candidates[:top_k]


def budget_note(candidates: list[dict], profile: ShoppingProfile) -> str | None:
    """Plain-language note when nothing fits the stated budget, so the
    recommender can say so honestly instead of pretending."""
    from app.catalog.utils import parse_numeric

    if profile.budget_max is None or not candidates:
        return None
    prices = [parse_numeric(c.get("price")) for c in candidates]
    if any(p is not None and p <= profile.budget_max for p in prices):
        return None
    return "None of the matching products are within the stated budget; the closest options are above it."
