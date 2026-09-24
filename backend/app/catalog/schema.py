"""
Data-driven completeness rules for catalog rows.

Instead of a hand-maintained list of required specs per category, the
expected attributes of a category are learned from the catalog itself:
an attribute most products in a category have (see COMMON_THRESHOLD) is
"expected" for that category. A row missing one gets a best-effort LLM
fill from its name/description and is still indexed -- only rows missing
core identity fields are rejected.
"""
from collections import Counter
from collections.abc import Iterable

from app.catalog.utils import is_missing

CORE_REQUIRED = ("name", "category", "price")

# Share of a category's products that must have an attribute before it is
# considered expected for the whole category.
COMMON_THRESHOLD = 0.6
# Categories smaller than this don't have enough data to infer anything.
MIN_ROWS_FOR_INFERENCE = 3


def missing_core(record: dict) -> list[str]:
    return [field for field in CORE_REQUIRED if is_missing(record.get(field))]


def expected_attributes(attribute_sets: Iterable[Iterable[str]]) -> set[str]:
    """Attributes present on at least COMMON_THRESHOLD of the given rows
    (each row given as the collection of attribute keys it has)."""
    rows = [set(keys) for keys in attribute_sets]
    if len(rows) < MIN_ROWS_FOR_INFERENCE:
        return set()
    counts = Counter(key for keys in rows for key in keys)
    return {key for key, n in counts.items() if n / len(rows) >= COMMON_THRESHOLD}


def missing_expected(attributes: dict, expected: set[str]) -> set[str]:
    return {key for key in expected if is_missing(attributes.get(key))}
