"""
Pure, framework-agnostic product-catalog tools backed directly by MySQL.

These are the "hands" behind the agentic layer: search, product detail
lookup, comparison, inventory and price checks. They're deliberately plain
functions with no CrewAI/MCP/LangChain imports, so they can be:

  1. Called in-process by the CrewAI product agent (see
     AGENTS/SALES_CREW_FACTORY.py) for zero-latency tool use during a crew
     run.
  2. Registered as MCP tools by MCP/server.py, so any external MCP client
     (Claude Desktop, Claude Code, another agent) can call the exact same
     catalog operations over the Model Context Protocol.
  3. Unit tested directly, with no LLM or MCP transport involved.

The product catalog schema (see DATABASE/SQL_CONNECTOR.py's document
builders) is intentionally treated as loosely typed: `ram`/`storage` are
free-text like "16GB", there's no `id` column (products are addressed by
name), and there's no dedicated inventory/rating table. Every function here
degrades gracefully instead of raising when a column is missing --
`check_inventory` and the "rating" contribution to recommendation scoring
(see WORKFLOW/scoring.py) both document this as a real limitation rather
than faking data that doesn't exist in the sample schema.
"""
import difflib
import logging
import re
from typing import Optional

import pandas as pd

from DATABASE.SQL_CONNECTOR import TABLES, build_engine

logger = logging.getLogger("agentic_salesman.tools")

CURRENCY = "INR"


class ProductToolError(ValueError):
    """Raised for caller errors (bad category, unknown product) -- never
    for infrastructure failures, which are allowed to propagate as-is so
    callers/tests can tell the two apart."""


def _validate_category(category: str) -> str:
    key = (category or "").strip().lower()
    if key not in TABLES:
        raise ProductToolError(
            f"Unknown category '{category}'. Expected one of: {', '.join(TABLES)}"
        )
    return key


def _load_table(category: str) -> pd.DataFrame:
    """Loads a product table fresh from MySQL. A short-lived engine per call
    mirrors check_mysql_connectivity()'s pattern -- these tools are called
    occasionally (a handful of times per chat turn at most), not in a hot
    loop, so pooling isn't worth the added complexity/thread-safety
    surface."""
    key = _validate_category(category)
    engine = build_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {TABLES[key]}", engine)
    finally:
        engine.dispose()


def parse_numeric(value) -> Optional[float]:
    """Best-effort numeric extraction from values like 16, "16", "16GB",
    "1TB" (-> 1000, treated as GB), "₹45,999". Returns None rather than
    raising when nothing numeric is found -- callers treat that as "unknown"
    and skip the corresponding filter/score contribution instead of
    crashing on a catalog they don't fully control the shape of."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0).replace(",", ""))
    if "tb" in text.lower():
        number *= 1000
    return number


def _find_row(df: pd.DataFrame, product_name: str) -> Optional[pd.Series]:
    if df.empty or "name" not in df.columns:
        return None
    exact = df[df["name"].astype(str).str.lower() == product_name.strip().lower()]
    if not exact.empty:
        return exact.iloc[0]

    close = difflib.get_close_matches(
        product_name, df["name"].astype(str).tolist(), n=1, cutoff=0.6
    )
    if close:
        return df[df["name"].astype(str) == close[0]].iloc[0]
    return None


def _inventory_columns(df: pd.DataFrame) -> Optional[str]:
    for candidate in ("stock", "quantity", "qty", "in_stock", "available"):
        for col in df.columns:
            if col.lower() == candidate:
                return col
    return None


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------
def search_products(
    category: str,
    max_price: Optional[float] = None,
    min_ram_gb: Optional[float] = None,
    min_storage_gb: Optional[float] = None,
    brand: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 10,
) -> list:
    """Structured catalog search -- exact filtering on price/spec/brand
    columns, unlike the semantic search in WORKFLOW/retrieval.py. Returns a
    list of plain dicts (JSON-serializable), sorted by price ascending.
    Every filter is optional; omitted ones are simply not applied."""
    df = _load_table(category)
    if df.empty:
        return []

    if max_price is not None and "price" in df.columns:
        df = df[df["price"].apply(parse_numeric).fillna(float("inf")) <= max_price]

    if min_ram_gb is not None and "ram" in df.columns:
        df = df[df["ram"].apply(parse_numeric).fillna(0) >= min_ram_gb]

    if min_storage_gb is not None and "storage" in df.columns:
        df = df[df["storage"].apply(parse_numeric).fillna(0) >= min_storage_gb]

    if brand and "brand" in df.columns:
        df = df[df["brand"].astype(str).str.lower() == brand.strip().lower()]

    if keyword and not df.empty:
        needle = keyword.strip().lower()
        text_cols = [c for c in df.columns if df[c].dtype == object]
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            mask = mask | df[col].astype(str).str.lower().str.contains(needle, na=False)
        df = df[mask]

    if "price" in df.columns:
        df = df.sort_values(by="price", key=lambda s: s.apply(parse_numeric))

    return df.head(limit).to_dict(orient="records")


def get_product_details(category: str, product_name: str) -> Optional[dict]:
    """Exact-or-fuzzy lookup of one product by name. Returns None (not an
    exception) when nothing matches closely enough -- "not found" is an
    expected, common outcome for a name typed by an LLM or a customer."""
    df = _load_table(category)
    row = _find_row(df, product_name)
    return None if row is None else row.to_dict()


def compare_products(category: str, product_names: list) -> dict:
    """Side-by-side comparison of 2+ products in the same category. Raises
    ProductToolError (a caller error, not an infra failure) if fewer than 2
    names resolve to real products -- there's nothing to compare
    otherwise."""
    if not product_names or len(product_names) < 2:
        raise ProductToolError("compare_products needs at least 2 product names")

    df = _load_table(category)
    found = {}
    missing = []
    for name in product_names:
        row = _find_row(df, name)
        if row is None:
            missing.append(name)
        else:
            found[str(row["name"])] = row.to_dict()

    if len(found) < 2:
        raise ProductToolError(
            f"Could only find {len(found)} of the requested products in '{category}' "
            f"(missing: {missing or 'n/a'}); need at least 2 to compare"
        )

    fields = sorted({key for product in found.values() for key in product})
    differences = [
        field
        for field in fields
        if len({str(product.get(field)) for product in found.values()}) > 1
    ]

    return {
        "category": category,
        "products": found,
        "differing_fields": differences,
        "missing": missing,
    }


def check_inventory(category: str, product_name: str) -> dict:
    """Availability check. The sample catalog has no dedicated inventory
    table/column, so this is intentionally conservative: a product that
    exists in the catalog is reported in_stock (True) with a note that this
    reflects catalog presence, not a live stock count, unless the table
    genuinely has a stock/quantity/available-style column -- in which case
    that's used instead. Wiring a real inventory system is called out in
    the README's Future Improvements rather than faked here."""
    df = _load_table(category)
    row = _find_row(df, product_name)
    if row is None:
        raise ProductToolError(f"No product matching '{product_name}' in '{category}'")

    inventory_col = _inventory_columns(df)
    if inventory_col:
        raw = row[inventory_col]
        quantity = parse_numeric(raw)
        in_stock = bool(quantity) if quantity is not None else bool(raw)
        return {
            "product": row["name"],
            "in_stock": in_stock,
            "quantity": quantity,
            "source": inventory_col,
        }

    return {
        "product": row["name"],
        "in_stock": True,
        "quantity": None,
        "source": "catalog-presence",
        "note": (
            "This catalog has no dedicated inventory column, so availability "
            "reflects that the product exists in MySQL, not a live stock count."
        ),
    }


def get_current_price(category: str, product_name: str) -> dict:
    """Point lookup of a single product's price. Kept separate from
    get_product_details (rather than just telling callers to read
    ["price"]) because it's a natural, common tool call on its own -- "what
    does the X cost right now" -- and mirrors the draft architecture's tool
    layer 1:1."""
    df = _load_table(category)
    row = _find_row(df, product_name)
    if row is None:
        raise ProductToolError(f"No product matching '{product_name}' in '{category}'")

    price = parse_numeric(row.get("price")) if "price" in df.columns else None
    return {"product": row["name"], "price": price, "currency": CURRENCY}
