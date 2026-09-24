"""Store identity and physical locations, read from settings."""
import re

from app.core.config import get_settings


def company_info() -> dict:
    s = get_settings()
    stores = s.stores
    return {
        "name": s.company_name,
        "tagline": s.company_tagline,
        "website": s.company_website,
        "support_phone": s.company_support_phone,
        "currency": s.company_currency,
        "store_count": len(stores),
        "cities": sorted({st.get("city") for st in stores if st.get("city")}),
    }


def list_stores(city: str | None = None) -> list[dict]:
    stores = get_settings().stores
    if not city or not city.strip():
        return list(stores)
    needle = city.strip().lower()
    return [st for st in stores if needle in str(st.get("city", "")).lower()]


def _name_variants(store_name: str) -> list[str]:
    """'Trein T Nagar' -> ['trein t nagar', 't nagar']: catalog text often
    omits the company prefix ("Available at Trein T Nagar, Koramangala")."""
    name = store_name.strip().lower()
    variants = [name] if name else []
    prefix = get_settings().company_name.strip().lower() + " "
    if prefix.strip() and name.startswith(prefix) and len(name) > len(prefix):
        variants.append(name[len(prefix):].strip())
    return variants


def _mentions(text: str, phrase: str) -> bool:
    return bool(phrase) and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def stores_carrying(offline_availability) -> list[dict]:
    """The configured stores named in a product's free-text offline
    availability ("Available at Trein T Nagar, Koramangala")."""
    text = str(offline_availability or "").lower()
    if not text.strip():
        return []
    return [
        store for store in get_settings().stores
        if any(_mentions(text, v) for v in _name_variants(str(store.get("name", ""))))
    ]


def available_in_city(offline_availability, city: str | None) -> bool:
    city = (city or "").strip().lower()
    if not city:
        return False
    text = str(offline_availability or "").lower()
    if _mentions(text, city):
        return True
    return any(str(s.get("city", "")).strip().lower() == city for s in stores_carrying(text))
