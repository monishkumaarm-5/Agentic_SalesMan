"""
Minimal per-category schema for RAG eligibility.

A product must have `name`, `brand` and `price` (universal, any category)
plus every field listed for its category below before it is allowed into
the Chroma vector store -- see DATABASE/SQL_CONNECTOR.py's
_product_documents, which calls missing_fields() as an ingestion-time
gate. Everything else is optional: it enriches search and display
(frontend/src/utils/specRules.js's SPEC_LABELS is the same vocabulary,
used there for display/quality-badge purposes rather than validation)
but a product missing it is still useful to RAG over.

The lists below are deliberately grounded in what the shipped sample
catalog already collects per category (sql/sample_data_products.sql --
every field here is present on 100% of that sample data), so turning
this gate on doesn't silently exclude the existing catalog. A category
not listed here (a genuinely new one) only has to satisfy the universal
CORE_REQUIRED fields -- it is never blocked just because nobody has
taught this module its field names yet.
"""

CORE_REQUIRED = ("name", "brand", "price")

REQUIRED_FIELDS = {
    "MOBILE": {"ram", "storage", "battery"},
    "LAPTOP": {"processor", "ram", "storage", "display"},
    "TABLET": {"processor", "ram", "storage", "display"},
    "HEADPHONE": {"type", "battery_life", "noise_cancellation"},
    "SPEAKER": {"type", "battery_life", "connectivity"},
    "SMARTWATCH": {"display", "battery_life", "water_resistance"},
    "TELEVISION": {"screen_size", "resolution", "type"},
    "REFRIGERATOR": {"capacity", "star_rating", "type"},
    "WASHING_MACHINE": {"capacity", "spin_speed", "star_rating"},
    "AIR_CONDITIONER": {"capacity", "star_rating", "inverter"},
    "MICROWAVE_OVEN": {"capacity", "power", "type"},
    "MIXER_GRINDER": {"power", "jars", "speed_settings"},
}

# A handful of fields have been stored under more than one key across
# older/newer rows -- checked in order, first present wins. Mirrors the
# alias pattern WORKFLOW/recommendations.py already uses for MRP/stock/
# online-link columns (MRP_COLUMNS, ONLINE_LINK_COLUMNS, etc).
FIELD_ALIASES = {
    "display": ("display", "screen_size"),
    "screen_size": ("screen_size", "display"),
}


def _category_key(category) -> str:
    return (str(category) if category is not None else "").strip().upper().replace(" ", "_")


def _is_present(record: dict, field: str) -> bool:
    for alias in FIELD_ALIASES.get(field, (field,)):
        value = record.get(alias)
        if value not in (None, ""):
            return True
    return False


def required_fields_for(category) -> set:
    """The category-specific required set. Empty for an unmapped/new
    category -- see module docstring."""
    return set(REQUIRED_FIELDS.get(_category_key(category), set()))


def missing_fields(category, record: dict) -> set:
    """`record` is a flattened dict -- core columns and attributes merged,
    the same shape DATABASE.SQL_CONNECTOR._product_documents already
    builds before this is called. Returns the set of required field names
    that are absent or empty; an empty set means the product is
    RAG-eligible as-is."""
    missing = {field for field in CORE_REQUIRED if record.get(field) in (None, "")}
    missing |= {
        field for field in required_fields_for(category)
        if not _is_present(record, field)
    }
    return missing


__all__ = [
    "CORE_REQUIRED",
    "REQUIRED_FIELDS",
    "FIELD_ALIASES",
    "required_fields_for",
    "missing_fields",
]
