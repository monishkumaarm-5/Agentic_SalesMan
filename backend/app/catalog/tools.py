"""
Framework-agnostic catalog operations: structured search, product
lookup, comparison, stock and price checks. Used by the chat workflow,
the REST API and the MCP server alike.
"""
import difflib
import logging
from collections.abc import Callable

import pandas as pd

from app.catalog.database import BOOKKEEPING_COLUMNS, load_products
from app.catalog.utils import clean_record, parse_numeric

logger = logging.getLogger("salesman.catalog.tools")

Loader = Callable[[str | None], pd.DataFrame]


class ProductToolError(ValueError):
    """A caller error (bad input, unknown product) -- not an outage."""


def _load(category: str | None, loader: Loader | None) -> pd.DataFrame:
    if category is not None and not str(category).strip():
        raise ProductToolError("A product category is required")
    return (loader or load_products)(category.strip() if category else None)


def _public(record: dict) -> dict:
    return {
        k: v for k, v in clean_record(record).items()
        if k not in BOOKKEEPING_COLUMNS and k != "attribute_keys"
    }


def find_row(df: pd.DataFrame, product_name: str, cutoff: float = 0.6) -> pd.Series | None:
    """Exact (case-insensitive) name match, then a fuzzy one."""
    if df.empty or "name" not in df.columns or not product_name:
        return None
    names = df["name"].astype(str)
    exact = df[names.str.lower() == product_name.strip().lower()]
    if not exact.empty:
        return exact.iloc[0]
    contained = df[names.str.lower().str.contains(product_name.strip().lower(), regex=False)]
    if len(contained) == 1:
        return contained.iloc[0]
    close = difflib.get_close_matches(product_name, names.tolist(), n=1, cutoff=cutoff)
    return df[names == close[0]].iloc[0] if close else None


def search_products(
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    brand: str | None = None,
    keyword: str | None = None,
    limit: int = 10,
    loader: Loader | None = None,
) -> list[dict]:
    """Structured search: exact price/brand filters plus a keyword that is
    matched against every text column, sorted by price ascending."""
    df = _load(category, loader)
    if df.empty:
        return []
    price = df["price"].apply(parse_numeric) if "price" in df.columns else None
    if price is not None:
        if max_price is not None:
            df = df[price.fillna(float("inf")) <= max_price]
        if min_price is not None:
            df = df[price.loc[df.index].fillna(0) >= min_price]
    if brand and "brand" in df.columns:
        df = df[df["brand"].astype(str).str.lower() == brand.strip().lower()]
    if keyword and not df.empty:
        needle = keyword.strip().lower()
        text_cols = [c for c in df.columns
                     if c != "attribute_keys" and (df[c].dtype == object or pd.api.types.is_string_dtype(df[c]))]
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            mask |= df[col].astype(str).str.lower().str.contains(needle, regex=False, na=False)
        df = df[mask]
    if "price" in df.columns and not df.empty:
        df = df.sort_values(by="price", key=lambda s: s.apply(parse_numeric))
    return [_public(r) for r in df.head(max(1, min(limit, 50))).to_dict(orient="records")]


def get_product_details(product_name: str, category: str | None = None,
                        loader: Loader | None = None) -> dict | None:
    row = find_row(_load(category, loader), product_name)
    return None if row is None else _public(row.to_dict())


def find_products(names: list[str], loader: Loader | None = None) -> list[dict]:
    """Looks up several products by (fuzzy) name across all categories in
    one query. Unknown names are skipped."""
    names = [n for n in names or [] if n and str(n).strip()]
    if not names:
        return []
    df = _load(None, loader)
    found, seen = [], set()
    for name in names:
        row = find_row(df, name)
        if row is not None and row.get("name") not in seen:
            seen.add(row.get("name"))
            found.append(clean_record({k: v for k, v in row.to_dict().items() if k not in BOOKKEEPING_COLUMNS}))
    return found


def compare_products(product_names: list[str], category: str | None = None,
                     loader: Loader | None = None) -> dict:
    if not product_names or len(product_names) < 2:
        raise ProductToolError("Need at least 2 product names to compare")
    df = _load(category, loader)
    found, missing = {}, []
    for name in product_names:
        row = find_row(df, name)
        if row is None:
            missing.append(name)
        else:
            record = _public(row.to_dict())
            record.pop("id", None)
            found[str(row["name"])] = record
    if len(found) < 2:
        raise ProductToolError(
            f"Found only {len(found)} of the requested products (missing: {', '.join(missing) or 'n/a'})"
        )
    fields = sorted({k for p in found.values() for k in p})
    differing = [f for f in fields if len({str(p.get(f)) for p in found.values()}) > 1]
    return {"category": category, "products": found, "differing_fields": differing, "missing": missing}


def check_inventory(product_name: str, category: str | None = None,
                    loader: Loader | None = None) -> dict:
    df = _load(category, loader)
    row = find_row(df, product_name)
    if row is None:
        raise ProductToolError(f"No product matching '{product_name}'")
    units = parse_numeric(row.get("units_available")) if "units_available" in df.columns else None
    return {
        "product": row["name"],
        "units_available": units,
        "in_stock": None if units is None else units > 0,
        "offline_availability": clean_record({"v": row.get("offline_availability")})["v"],
    }


def get_current_price(product_name: str, category: str | None = None,
                      loader: Loader | None = None) -> dict:
    row = find_row(_load(category, loader), product_name)
    if row is None:
        raise ProductToolError(f"No product matching '{product_name}'")
    return {"product": row["name"], "price": parse_numeric(row.get("price")),
            "mrp": parse_numeric(row.get("mrp"))}
