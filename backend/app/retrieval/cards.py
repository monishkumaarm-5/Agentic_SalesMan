"""
Customer-facing product cards. Every fact on a card (price, stock,
stores, specs, links) comes straight from the catalog; only the
narrative fields come from the recommender agent.
"""
import difflib

from app import company
from app.catalog.utils import humanize, is_missing, parse_numeric
from app.core.config import get_settings

_NOT_SPECS = {
    "id", "name", "category", "brand", "price", "mrp", "units_available", "rating",
    "online_link", "offline_availability", "description", "customer_feedback",
    "attribute_keys", "ingestion_status", "ingestion_missing_fields", "created_at", "updated_at",
}


def _specs(row: dict) -> list[dict]:
    keys = row.get("attribute_keys") or [
        k for k in row if k not in _NOT_SPECS and not str(k).startswith("_")
    ]
    return [
        {"key": k, "label": humanize(k), "value": str(row[k])}
        for k in keys if k in row and not is_missing(row[k])
    ]


def _stores(row: dict, city: str | None) -> list[dict]:
    city_l = (city or "").strip().lower()
    stores = []
    for store in company.stores_carrying(row.get("offline_availability")):
        stores.append({
            **store,
            "nearby": bool(city_l) and str(store.get("city", "")).lower() == city_l,
            "maps_url": "https://www.google.com/maps/search/?api=1&query="
                        + _quote(store.get("address") or store.get("name", "")),
        })
    stores.sort(key=lambda s: not s["nearby"])
    return stores


def _quote(text: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(str(text))


def build_card(row: dict, narrative: dict | None = None, rank: int = 1,
               city: str | None = None) -> dict:
    narrative = narrative or {}
    price = parse_numeric(row.get("price"))
    mrp = parse_numeric(row.get("mrp"))
    units = parse_numeric(row.get("units_available"))
    rating = parse_numeric(row.get("rating"))
    scores = row.get("_scores") or {}
    return {
        "rank": rank,
        "id": row.get("id"),
        "name": row.get("name"),
        "brand": row.get("brand"),
        "category": row.get("category"),
        "price": price,
        "mrp": mrp if mrp and price and mrp > price else None,
        "discount_percent": round((mrp - price) / mrp * 100) if mrp and price and mrp > price else None,
        "currency": get_settings().company_currency,
        "rating": rating,
        "units_available": int(units) if units is not None else None,
        "in_stock": None if units is None else units > 0,
        "online_link": None if is_missing(row.get("online_link")) else row.get("online_link"),
        "offline_availability": None if is_missing(row.get("offline_availability")) else row.get("offline_availability"),
        "stores": _stores(row, city),
        "description": None if is_missing(row.get("description")) else row.get("description"),
        "specs": _specs(row),
        "headline": narrative.get("headline") or None,
        "why": narrative.get("why") or None,
        "key_features": [f for f in narrative.get("key_features") or [] if f],
        "fit_reasons": scores.get("reasons") or [],
        "match": {"overall": scores.get("overall"), "components": scores.get("components") or {}},
    }


def match_name(name: str, candidates: list[dict]) -> dict | None:
    """Maps an LLM-written product name back onto a real candidate."""
    if not name:
        return None
    lowered = name.strip().lower()
    for c in candidates:
        if str(c.get("name") or "").strip().lower() == lowered:
            return c
    for c in candidates:
        cname = str(c.get("name") or "").strip().lower()
        if cname and (cname in lowered or lowered in cname):
            return c
    names = [str(c.get("name") or "") for c in candidates]
    close = difflib.get_close_matches(name, names, n=1, cutoff=0.75)
    return next((c for c in candidates if c.get("name") == close[0]), None) if close else None
