"""Formats live store/catalog/conversation context for the prompts."""
import json

from app.catalog.utils import format_price, is_missing
from app.core.config import get_settings
from app.models import ShoppingProfile


def store_context() -> str:
    s = get_settings()
    lines = [
        f"Name: {s.company_name} -- {s.company_tagline}",
        f"Website: {s.company_website}",
        f"Support phone: {s.company_support_phone}",
    ]
    stores = s.stores
    if stores:
        lines.append("Showrooms:")
        lines += [
            f"- {st.get('name')} ({st.get('city')}): {st.get('address')}; {st.get('hours') or ''}; phone {st.get('phone') or 'n/a'}"
            for st in stores
        ]
    else:
        lines.append("Showrooms: none (online only)")
    return "\n".join(lines)


def catalog_context(overview: list[dict]) -> str:
    if not overview:
        return "(catalog currently unavailable)"
    currency = get_settings().company_currency
    lines = []
    for c in overview:
        price = ""
        if c.get("min_price") is not None:
            price = f", {format_price(c['min_price'], currency)} - {format_price(c['max_price'], currency)}"
        brands = ", ".join(c.get("brands", [])[:12])
        lines.append(f"- {c['name']}: {c['product_count']} products{price}; brands: {brands or 'n/a'}")
    return "\n".join(lines)


def profile_context(profile: ShoppingProfile) -> str:
    data = profile.model_dump(exclude_none=True)
    data = {k: v for k, v in data.items() if v not in ([], "")}
    return json.dumps(data, ensure_ascii=False) if data else "{} (nothing known yet)"


def shown_context(shown: dict) -> str:
    """Products already shown to the customer, most recent set per category."""
    if not shown:
        return "(none yet)"
    currency = get_settings().company_currency
    lines = []
    for category, cards in shown.items():
        for i, card in enumerate(cards or [], start=1):
            lines.append(f"- [{category} #{i}] {card.get('name')} by {card.get('brand')}, "
                         f"{format_price(card.get('price'), currency)}")
    return "\n".join(lines) or "(none yet)"


def history_context(messages: list[dict], window: int) -> str:
    recent = [m for m in messages if m.get("content")][-window:]
    if not recent:
        return "(this is the first message)"
    return "\n".join(f"{m['role'].upper()}: {_short(m['content'], 700)}" for m in recent)


def product_facts(row: dict, currency: str = "INR", review_chars: int = 350) -> str:
    """One product's catalog facts as a compact line block for grounding."""
    skip = {"id", "name", "brand", "category", "price", "mrp", "rating", "units_available",
            "online_link", "offline_availability", "description", "customer_feedback", "attribute_keys"}
    facts = [f"{row.get('name')} | brand {row.get('brand')} | {format_price(row.get('price'), currency)}"]
    if not is_missing(row.get("mrp")):
        facts.append(f"MRP {format_price(row.get('mrp'), currency)}")
    if not is_missing(row.get("rating")):
        facts.append(f"rating {row.get('rating')}/5")
    if not is_missing(row.get("units_available")):
        facts.append(f"{row.get('units_available')} in stock")
    if not is_missing(row.get("offline_availability")):
        facts.append(f"stores: {row.get('offline_availability')}")
    specs = row.get("specs")
    if isinstance(specs, list):
        spec_text = ", ".join(f"{s['label']}: {s['value']}" for s in specs)
    else:
        spec_text = ", ".join(f"{k}: {v}" for k, v in row.items()
                              if k not in skip and not str(k).startswith("_") and not is_missing(v))
    lines = [" | ".join(facts)]
    if spec_text:
        lines.append(f"   specs: {spec_text}")
    if not is_missing(row.get("description")):
        lines.append(f"   about: {row.get('description')}")
    if review_chars and not is_missing(row.get("customer_feedback")):
        lines.append(f"   reviews: {_short(str(row['customer_feedback']), review_chars)}")
    return "\n".join(lines)


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
