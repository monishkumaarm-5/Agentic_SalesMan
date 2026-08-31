"""
Recommendation scoring: turns a retrieved candidate product + the
customer's extracted requirements into a single, explainable "why this one"
score, instead of trusting semantic similarity alone.

score = semantic * 0.30 + budget_fit * 0.25 + spec_match * 0.20
        + rating * 0.15 + brand_fit * 0.10

The sample catalog (see DATABASE/SQL_CONNECTOR.py's document builders) has
no rating column, so `rating` is dropped and its weight is redistributed
proportionally across the other four components whenever a candidate has no
rating-like field -- rather than silently treating a missing rating as 0
(which would unfairly tank every product) or faking a number. If a real
catalog later adds a rating/stars/review_score column, it's picked up
automatically.

Every component score is bounded to [0, 1] so weighted sums stay in [0, 1].
"""
from typing import Optional

from TOOLS.product_tools import parse_numeric

BASE_WEIGHTS = {
    "semantic": 0.30,
    "budget_fit": 0.25,
    "spec_match": 0.20,
    "rating": 0.15,
    "brand_fit": 0.10,
}

NEUTRAL = 0.7  # score used when a signal is simply unavailable (not "bad")

# Coarse keyword -> spec-requirement mapping used by _spec_match_score.
# Deliberately simple/deterministic (no extra LLM call) -- good enough to
# meaningfully separate candidates, not meant to be a real ML model.
USE_CASE_HINTS = {
    "machine learning": {"min_ram_gb": 16, "keywords": ("gpu", "rtx", "gtx", "nvidia")},
    "ml": {"min_ram_gb": 16, "keywords": ("gpu", "rtx", "gtx", "nvidia")},
    "docker": {"min_ram_gb": 8, "keywords": ()},
    "gaming": {"min_ram_gb": 16, "keywords": ("gpu", "rtx", "gtx", "radeon")},
    "video editing": {"min_ram_gb": 16, "keywords": ("gpu",)},
    "photo editing": {"min_ram_gb": 8, "keywords": ()},
    "programming": {"min_ram_gb": 8, "keywords": ()},
    "coding": {"min_ram_gb": 8, "keywords": ()},
    "development": {"min_ram_gb": 8, "keywords": ()},
    "student": {"min_ram_gb": 4, "keywords": ()},
    "office": {"min_ram_gb": 4, "keywords": ()},
    "battery life": {"min_ram_gb": None, "keywords": ("battery",)},
    "noise cancelling": {"min_ram_gb": None, "keywords": ("anc", "noise")},
    "noise cancellation": {"min_ram_gb": None, "keywords": ("anc", "noise")},
    "camera": {"min_ram_gb": None, "keywords": ("camera", "mp", "megapixel")},
}

RATING_COLUMN_NAMES = ("rating", "stars", "review_score", "avg_rating")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def budget_fit_score(price, budget_max: Optional[float]) -> float:
    price_value = parse_numeric(price)
    if budget_max is None or price_value is None:
        return NEUTRAL
    if price_value <= budget_max:
        return 1.0
    overage_ratio = (price_value - budget_max) / budget_max
    return _clamp(1.0 - overage_ratio)


def spec_match_score(row: dict, use_cases: list) -> float:
    if not use_cases:
        return NEUTRAL

    haystack = " ".join(str(v) for v in row.values() if v is not None).lower()
    ram = parse_numeric(row.get("ram"))

    score = 0.4  # baseline: some credit just for being retrieved at all
    hints_matched = 0
    for use_case in use_cases:
        hint = USE_CASE_HINTS.get(str(use_case).strip().lower())
        if not hint:
            continue
        hints_matched += 1
        if hint["min_ram_gb"] is not None and ram is not None and ram >= hint["min_ram_gb"]:
            score += 0.2
        if hint["keywords"] and any(kw in haystack for kw in hint["keywords"]):
            score += 0.2

    if hints_matched == 0:
        # None of the use cases matched a known hint -- neutral rather than
        # penalizing a product for a requirement we simply can't evaluate.
        return NEUTRAL

    return _clamp(score)


def rating_score(row: dict):
    """Returns (score, available). available=False means the caller should
    drop the rating component and redistribute its weight."""
    for key, value in row.items():
        if key.lower() in RATING_COLUMN_NAMES:
            number = parse_numeric(value)
            if number is None:
                continue
            scale = 10.0 if number > 5 else 5.0
            return _clamp(number / scale), True
    return 0.0, False


def brand_fit_score(product_brand, requested_brand: Optional[str]) -> float:
    if not requested_brand:
        return NEUTRAL
    if not product_brand:
        return 0.5
    return 1.0 if str(product_brand).strip().lower() == requested_brand.strip().lower() else 0.3


def score_candidate(row: dict, requirements: dict, semantic_score: float) -> dict:
    """requirements: {"budget_max": float|None, "use_cases": list[str],
    "brand": str|None}. semantic_score must already be normalized to
    [0, 1] (higher = more relevant) -- see WORKFLOW/retrieval.py."""
    requirements = requirements or {}
    semantic_score = _clamp(semantic_score)

    components = {
        "semantic": semantic_score,
        "budget_fit": budget_fit_score(row.get("price"), requirements.get("budget_max")),
        "spec_match": spec_match_score(row, requirements.get("use_cases") or []),
        "brand_fit": brand_fit_score(row.get("brand"), requirements.get("brand")),
    }

    rating, rating_available = rating_score(row)
    weights = dict(BASE_WEIGHTS)
    if rating_available:
        components["rating"] = rating
    else:
        removed = weights.pop("rating")
        remaining_total = sum(weights.values())
        weights = {k: v + (v / remaining_total) * removed for k, v in weights.items()}

    overall = sum(components[key] * weights[key] for key in components)

    return {
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "rating_available": rating_available,
        "overall": round(_clamp(overall), 4),
    }
