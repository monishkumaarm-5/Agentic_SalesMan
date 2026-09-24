"""
Builds the rich "top pick" cards the API returns under ChatResponse.product
(`{"top_picks": [...]}`) and the frontend renders as one set of cards per
recommended product: Why this / Key Features / Why this suits you / Buy Now
(see frontend/src/components/TopPicks.jsx).

Two kinds of data go into a pick, kept deliberately separate so the sales
agent's LLM can never invent numbers:

  1. Deterministic, straight from the scored retrieval candidate (see
     WORKFLOW/retrieval.py + WORKFLOW/scoring.py): specs, price, and --
     only when the catalog actually has the column -- mrp/discount, stock
     units, an online purchase link and offline-store availability. A
     column the catalog doesn't have yields `None` (rendered by the
     frontend as "Not available"), never a guess.

  2. The LLM's narrative for that specific product (why_this,
     key_features, why_suits_you), matched back onto the candidate by
     name (exact, then fuzzy) so a slightly-off product name from the
     model still lands on the right card instead of being silently
     dropped.

Ranking always comes from the deterministic retrieval score (candidates
are already sorted best-first by hybrid_search), never from the order the
LLM happens to list products in -- so "top pick" can't be quietly
reshuffled by the model.
"""
import difflib
import logging
import re
from typing import Optional
from urllib.parse import quote as _urlquote

import config
from TOOLS.product_tools import parse_numeric

logger = logging.getLogger("agentic_salesman.recommendations")

TOP_PICKS_COUNT = 3

# Optional catalog columns -- checked case-insensitively, first match wins.
# None of these are required; every one degrades to `None` rather than
# being faked when the catalog doesn't track it.
MRP_COLUMNS = ("mrp", "original_price", "list_price", "strike_price")
UNITS_COLUMNS = ("units_available", "stock", "quantity", "qty", "units")
STOCK_FLAG_COLUMNS = ("in_stock", "available")
ONLINE_LINK_COLUMNS = ("online_link", "buy_link", "purchase_link", "product_url", "url", "link")
OFFLINE_COLUMNS = ("offline_availability", "offline_stores", "in_store", "store_availability")

# Substrings that mean "this row explicitly has no offline availability" --
# never matched against STORE_LOCATIONS, never shown as a store list.
_NO_OFFLINE_PHRASES = ("not available in offline", "online only", "online-only")

# Fields already surfaced elsewhere on a pick card (build_buy_info, or the
# card's own name/category) or purely internal bookkeeping -- never shown a
# second time as a generic "spec" pill. This used to be a fixed allowlist
# of phone/laptop/headphone columns (brand/processor/ram/storage/color/
# type/quality); now that the catalog is one generic `products` table with
# a category-specific `attributes` JSON blob (see
# DATABASE/SQL_CONNECTOR.py), specs are whatever's left after excluding
# this small denylist -- so a brand new category (capacity/star_rating for
# a fridge, screen_size for a TV, ...) shows up automatically with zero
# code changes here.
NON_SPEC_FIELDS = {
    "id", "name", "category", "price", "mrp", "units_available",
    "in_stock", "online_link", "offline_availability", "description",
    "customer_feedback", "created_at", "updated_at",
    "ingestion_status", "ingestion_missing_fields",
    "_page_content", "_scores",
}


def _first_present(row: dict, columns: tuple):
    """Case-insensitive lookup of the first of `columns` that exists in
    `row` with a non-empty value. Returns None if none match -- the
    signal callers use to mean "this catalog doesn't track that"."""
    lower_map = {str(key).lower(): key for key in row.keys()}
    for name in columns:
        actual_key = lower_map.get(name)
        if actual_key is None:
            continue
        value = row.get(actual_key)
        if value is not None and value != "":
            return value
    return None


def _maps_url(address: str) -> str:
    """A Google Maps search URL for a physical address -- opens directly
    to that location (not a generic "showroom near me" search) when
    followed in a browser. Same construction as the frontend's
    utils/format.js:mapsSearchUrl, duplicated here (not imported) because
    this is Python computing a value for an API response, not a UI
    concern -- the frontend just renders the link build_buy_info hands
    it."""
    return f"https://www.google.com/maps/search/{_urlquote(address)}"


def _match_offline_stores(offline_availability) -> list:
    """Matches a catalog row's free-text `offline_availability` column
    (e.g. "Available at Trein T Nagar, Koramangala") against
    config.STORE_LOCATIONS, so the frontend can show a Maps link to each
    SPECIFIC branch that actually carries this product -- not a generic
    "<brand> showroom near me" search that ignores which of several
    branches (or none) has it.

    Matching is deliberately loose (case-insensitive substring, either
    direction) because this column is free text a catalog owner typed,
    not a foreign key: "Trein T Nagar" in the text matches a store named
    "Trein T Nagar"; the shorter "Koramangala" in the text still matches
    a store named "Trein Koramangala" via a store-name-contains-token
    check.

    A row can legitimately reference stores that AREN'T in
    STORE_LOCATIONS at all -- e.g. "Croma, Reliance Digital" -- when a
    catalog tracks third-party retail availability rather than the
    company's own showrooms. That's not a matching failure: it just
    means an empty list here, with the raw text still available in
    build_buy_info's `offline_availability` for display. Returns []
    (never None) so the frontend can always .map() over it safely.
    """
    if not offline_availability:
        return []

    text = str(offline_availability).strip()
    lowered = text.lower()
    if not text or any(phrase in lowered for phrase in _NO_OFFLINE_PHRASES):
        return []

    # Strip a leading "Available at " (or similar) so token-matching isn't
    # thrown off by it; harmless no-op if the text doesn't start that way.
    lowered = re.sub(r"^\s*available\s+(at|in)\s*:?\s*", "", lowered)

    tokens = [token.strip() for token in re.split(r"[,;]", lowered) if token.strip()]
    if not tokens:
        tokens = [lowered]

    stores = getattr(config, "STORE_LOCATIONS", None) or []
    matched = []
    seen_names = set()

    for store in stores:
        store_name = str(store.get("name", "")).strip()
        if not store_name or store_name in seen_names:
            continue
        store_name_lower = store_name.lower()

        is_match = any(
            token in store_name_lower or store_name_lower in token
            for token in tokens
        )
        if not is_match:
            continue

        seen_names.add(store_name)
        address = store.get("address") or store_name
        matched.append(
            {
                "name": store_name,
                "city": store.get("city"),
                "address": store.get("address"),
                "phone": store.get("phone"),
                "hours": store.get("hours"),
                "maps_url": _maps_url(address),
            }
        )

    return matched


def build_buy_info(row: dict) -> dict:
    """Deterministic purchase details for one candidate row: price plus
    whatever optional discount/stock/link/offline-availability columns the
    catalog happens to have. Every field the catalog doesn't track comes
    back as None -- the frontend shows that as "Not available" rather than
    a fabricated number (see module docstring)."""
    price = parse_numeric(row.get("price"))
    mrp = parse_numeric(_first_present(row, MRP_COLUMNS))

    discount_percentage = None
    if price is not None and mrp is not None and mrp > price:
        discount_percentage = round((mrp - price) / mrp * 100, 1)

    units_available = parse_numeric(_first_present(row, UNITS_COLUMNS))
    stock_flag = _first_present(row, STOCK_FLAG_COLUMNS)

    if units_available is not None:
        in_stock = units_available > 0
    elif stock_flag is not None:
        in_stock = bool(stock_flag) and str(stock_flag).strip().lower() not in ("0", "false", "no")
    else:
        in_stock = None

    offline_availability = _first_present(row, OFFLINE_COLUMNS)

    return {
        "price": price,
        "currency": "INR",
        "mrp": mrp,
        "discount_percentage": discount_percentage,
        "units_available": units_available,
        "in_stock": in_stock,
        "online_link": _first_present(row, ONLINE_LINK_COLUMNS),
        "offline_availability": offline_availability,
        "offline_stores": _match_offline_stores(offline_availability),
    }


def _specs(row: dict) -> dict:
    """Every field the catalog has for this product except the denylisted
    "already shown elsewhere / internal" ones -- see NON_SPEC_FIELDS."""
    return {
        key: value
        for key, value in row.items()
        if key not in NON_SPEC_FIELDS
        and not str(key).startswith("_")
        and value not in (None, "")
    }


def _match_narrative(name: Optional[str], narratives: list) -> Optional[dict]:
    """Best-effort match of one LLM-authored pick (identified by product
    name) onto a candidate. Exact case-insensitive match first, then a
    fuzzy match -- mirrors TOOLS/product_tools._find_row's tolerance for a
    slightly-off name from the model."""
    if not name or not narratives:
        return None

    lowered = name.strip().lower()
    for entry in narratives:
        if str(entry.get("name") or "").strip().lower() == lowered:
            return entry

    candidate_names = [str(entry.get("name") or "") for entry in narratives]
    close = difflib.get_close_matches(name, candidate_names, n=1, cutoff=0.6)
    if close:
        for entry in narratives:
            if str(entry.get("name") or "") == close[0]:
                return entry
    return None


def build_top_picks(
    candidates: list,
    narratives: Optional[list] = None,
    top_n: int = TOP_PICKS_COUNT,
) -> list:
    """candidates: the score-sorted list from WORKFLOW/retrieval.hybrid_search
    (highest overall score first). narratives: the sales agent's own
    `top_picks` JSON -- a list of {name, why_this, key_features,
    why_suits_you} -- if it returned one and it parsed. Optional: a card
    with real price/specs/buy info is still worth showing even when the
    narrative text is missing or didn't parse.

    Returns up to `top_n` picks, each:
    {
        "rank": 1,
        "name": str | None,
        "specs": {...},               # deterministic, from the catalog
        "scores": {...} | None,       # WORKFLOW/scoring.py breakdown
        "buy": {...},                 # see build_buy_info
        "why_this": str | None,       # LLM narrative, matched by name
        "key_features": [...],
        "why_suits_you": str | None,
    }
    """
    narratives = narratives or []
    picks = []
    for rank, candidate in enumerate(candidates[:top_n], start=1):
        name = candidate.get("name")
        narrative = _match_narrative(name, narratives) or {}
        picks.append(
            {
                "rank": rank,
                "name": name,
                "specs": _specs(candidate),
                "scores": candidate.get("_scores"),
                "buy": build_buy_info(candidate),
                "why_this": narrative.get("why_this") or narrative.get("reason"),
                "key_features": narrative.get("key_features") or [],
                "why_suits_you": narrative.get("why_suits_you"),
            }
        )
    return picks
