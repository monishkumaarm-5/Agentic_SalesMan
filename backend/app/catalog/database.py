"""
MySQL access for the product catalog.

The catalog is one generic `products` table: core columns (name, brand,
price, ...) plus a JSON `attributes` column for category-specific specs,
so a new category is just new rows -- never new code.
"""
import logging
import threading
import time

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from app.catalog.utils import parse_attributes
from app.core.config import get_settings

logger = logging.getLogger("salesman.catalog.db")

PRODUCTS_TABLE = "products"

CORE_COLUMNS = (
    "id", "category", "name", "brand", "price", "mrp", "units_available",
    "rating", "online_link", "offline_availability", "description",
    "customer_feedback",
)

# Columns the sync process writes back; never part of a product's data.
BOOKKEEPING_COLUMNS = ("ingestion_status", "ingestion_missing_fields", "created_at", "updated_at")

_engine: Engine | None = None
_engine_lock = threading.Lock()


def connection_url() -> URL:
    s = get_settings()
    return URL.create(
        drivername="mysql+pymysql",
        username=s.db_username,
        password=s.db_password,
        host=s.db_host,
        port=s.db_port,
        database=s.db_name,
    )


def get_engine() -> Engine:
    """Process-wide pooled engine."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = create_engine(
                    connection_url(),
                    pool_size=5,
                    max_overflow=10,
                    pool_recycle=1800,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 10},
                )
    return _engine


def reset_engine() -> None:
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None


def check_connectivity(timeout_seconds: int = 3) -> None:
    """Raises if MySQL is unreachable."""
    engine = create_engine(connection_url(), connect_args={"connect_timeout": timeout_seconds})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def expand_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """Flattens the JSON `attributes` column into ordinary columns and
    records which keys came from it in `attribute_keys` (a list per row).
    Core columns win over same-named attributes."""
    if df.empty:
        df = df.copy()
        df["attribute_keys"] = pd.Series(dtype=object)
        return df.drop(columns=["attributes"], errors="ignore")

    parsed = df["attributes"].apply(parse_attributes) if "attributes" in df.columns else pd.Series([{}] * len(df))
    base = df.drop(columns=["attributes"], errors="ignore").reset_index(drop=True)
    parsed = parsed.reset_index(drop=True).apply(
        lambda attrs: {k: v for k, v in attrs.items() if k not in base.columns}
    )
    attr_df = pd.DataFrame(list(parsed)) if len(parsed) else pd.DataFrame()
    out = pd.concat([base, attr_df], axis=1) if not attr_df.empty else base
    out["attribute_keys"] = parsed.apply(lambda attrs: [k for k, v in attrs.items() if v not in (None, "")])
    return out


def load_products(category: str | None = None, engine: Engine | None = None) -> pd.DataFrame:
    """All products (optionally one category, case-insensitive) with the
    JSON attributes flattened into columns."""
    return expand_attributes(load_raw_products(category, engine))


def load_raw_products(category: str | None = None, engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    if category:
        return pd.read_sql(
            text(f"SELECT * FROM {PRODUCTS_TABLE} WHERE LOWER(category) = LOWER(:category)"),
            engine,
            params={"category": category.strip()},
        )
    return pd.read_sql(text(f"SELECT * FROM {PRODUCTS_TABLE}"), engine)


# --- Category overview (cached) ------------------------------------------

_OVERVIEW_TTL_SECONDS = 300
_overview_cache: dict = {"value": None, "at": 0.0}
_overview_lock = threading.Lock()


def category_overview(force: bool = False) -> list[dict]:
    """[{name, product_count, min_price, max_price, brands}] for every
    category in the catalog -- the live context the agents reason over
    instead of a hard-coded category list. Cached for a few minutes;
    returns the last good value (or []) if MySQL is unavailable."""
    now = time.monotonic()
    cached = _overview_cache["value"]
    if not force and cached is not None and now - _overview_cache["at"] < _OVERVIEW_TTL_SECONDS:
        return cached

    with _overview_lock:
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(text(
                    f"SELECT category, COUNT(*) AS n, MIN(price) AS lo, MAX(price) AS hi, "
                    f"GROUP_CONCAT(DISTINCT brand ORDER BY brand SEPARATOR '|') AS brands "
                    f"FROM {PRODUCTS_TABLE} GROUP BY category ORDER BY category"
                )).fetchall()
        except Exception as exc:  # noqa: BLE001 - never break a chat turn
            logger.warning("Could not load category overview: %s", exc)
            return cached or []

        overview = [
            {
                "name": row[0],
                "product_count": int(row[1] or 0),
                "min_price": float(row[2]) if row[2] is not None else None,
                "max_price": float(row[3]) if row[3] is not None else None,
                "brands": [b for b in str(row[4] or "").split("|") if b],
            }
            for row in rows
            if row[0] and str(row[0]).strip()
        ]
        _overview_cache.update(value=overview, at=now)
        return overview


def list_categories() -> list[str]:
    return [entry["name"] for entry in category_overview()]


def clear_overview_cache() -> None:
    _overview_cache.update(value=None, at=0.0)
