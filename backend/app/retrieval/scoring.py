"""
Explainable product scoring against a ShoppingProfile.

Every component returns a score in [0, 1], or None when the signal simply
isn't available (no budget given, product has no rating, ...). Missing
components are dropped and their weight is shared out among the rest, so
a product is never penalised for data nobody asked about.

Feature matching is data-driven: the customer's own use cases and
must-haves are matched against the product's text, instead of a fixed
table of "gaming means 16GB RAM"-style rules.
"""
import re

from app import company
from app.catalog.utils import format_price, is_missing, parse_numeric
from app.models import ShoppingProfile

WEIGHTS = {
    "relevance": 0.30,
    "budget": 0.25,
    "features": 0.20,
    "rating": 0.10,
    "brand": 0.10,
    "availability": 0.05,
}

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOPWORDS = {
    "the", "and", "for", "with", "good", "great", "best", "very", "long", "high",
    "low", "must", "have", "need", "want", "that", "this", "use", "using", "any",
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _tokens(text: str) -> set[str]:
    raw = _TOKEN_RE.findall(text.lower())
    tokens = set(raw)
    # "16 gb" and "16gb" should match each other.
    tokens |= {a + b for a, b in zip(raw, raw[1:], strict=False) if a.replace(".", "").isdigit() and b.isalpha()}
    return tokens


def _significant(term: str) -> set[str]:
    return {t for t in _tokens(term) if t not in _STOPWORDS and (len(t) >= 2 or t.isdigit())}


def product_text(row: dict) -> str:
    return " ".join(
        f"{k} {v}" for k, v in row.items()
        if not str(k).startswith("_") and k not in ("online_link", "attribute_keys") and not is_missing(v)
    )


def budget_score(price, profile: ShoppingProfile) -> float | None:
    value = parse_numeric(price)
    if value is None or (profile.budget_max is None and profile.budget_min is None):
        return None
    if profile.budget_max is not None and value > profile.budget_max:
        return _clamp(1.0 - 2.0 * (value - profile.budget_max) / profile.budget_max)
    if profile.budget_min is not None and value < profile.budget_min:
        # Cheaper than they expected: fine, but maybe not what they want.
        return _clamp(0.9 - 0.5 * (profile.budget_min - value) / profile.budget_min)
    return 1.0


def feature_matches(row: dict, profile: ShoppingProfile) -> tuple[list[str], list[str]]:
    """(matched, unmatched) of the customer's must-haves and use cases."""
    haystack = _tokens(product_text(row))
    matched, unmatched = [], []
    for term in [*profile.must_haves, *profile.use_cases]:
        words = _significant(term)
        if not words:
            continue
        hit = len(words & haystack) / len(words)
        (matched if hit >= 0.5 else unmatched).append(term)
    return matched, unmatched


def features_score(row: dict, profile: ShoppingProfile) -> float | None:
    matched, unmatched = feature_matches(row, profile)
    total = len(matched) + len(unmatched)
    if not total:
        return None
    # Use cases rarely appear verbatim in specs, so a miss is only a mild
    # negative; a hit is a strong positive.
    return _clamp(0.35 + 0.65 * len(matched) / total)


def rating_score(row: dict) -> float | None:
    rating = parse_numeric(row.get("rating"))
    if rating is None or rating <= 0:
        return None
    return _clamp(rating / (10.0 if rating > 5 else 5.0))


def brand_score(row: dict, profile: ShoppingProfile) -> float | None:
    brand = str(row.get("brand") or "").strip().lower()
    if not brand or not (profile.preferred_brands or profile.avoid_brands):
        return None
    if brand in {b.lower() for b in profile.avoid_brands}:
        return 0.0
    if profile.preferred_brands:
        return 1.0 if brand in {b.lower() for b in profile.preferred_brands} else 0.4
    return 0.8


def availability_score(row: dict, profile: ShoppingProfile) -> float | None:
    units = parse_numeric(row.get("units_available"))
    stocked = None if units is None else units > 0
    in_city = company.available_in_city(row.get("offline_availability"), profile.city) if profile.city else None
    if stocked is None and in_city is None:
        return None
    score = 1.0 if stocked is not False else 0.2
    if in_city is False:
        score *= 0.75
    return score


def score_product(row: dict, profile: ShoppingProfile, relevance: float) -> dict:
    components = {
        "relevance": _clamp(relevance),
        "budget": budget_score(row.get("price"), profile),
        "features": features_score(row, profile),
        "rating": rating_score(row),
        "brand": brand_score(row, profile),
        "availability": availability_score(row, profile),
    }
    available = {k: v for k, v in components.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in available)
    overall = sum(v * WEIGHTS[k] for k, v in available.items()) / total_weight if total_weight else 0.0
    return {
        "overall": round(_clamp(overall), 4),
        "components": {k: round(v, 4) for k, v in available.items()},
        "reasons": fit_reasons(row, profile),
    }


def fit_reasons(row: dict, profile: ShoppingProfile, currency: str = "INR") -> list[str]:
    """Short, factual, customer-facing notes on how a product fits."""
    reasons = []
    price = parse_numeric(row.get("price"))
    if price is not None and profile.budget_max is not None:
        if price <= profile.budget_max:
            reasons.append(f"Within your {format_price(profile.budget_max, currency)} budget")
        else:
            reasons.append(f"{format_price(price - profile.budget_max, currency)} over your budget")
    matched, _ = feature_matches(row, profile)
    if matched:
        reasons.append("Matches: " + ", ".join(matched[:4]))
    rating = parse_numeric(row.get("rating"))
    if rating:
        reasons.append(f"Rated {rating:g}/5 by customers")
    brand = str(row.get("brand") or "")
    if brand and brand.lower() in {b.lower() for b in profile.preferred_brands}:
        reasons.append(f"Your preferred brand ({brand})")
    if profile.city and company.available_in_city(row.get("offline_availability"), profile.city):
        reasons.append(f"In stock at our {profile.city} store")
    return reasons
