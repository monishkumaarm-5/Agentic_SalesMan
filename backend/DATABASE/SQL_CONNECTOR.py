"""
Generic, category-agnostic catalog connector.

Single MySQL table (`products`) with a JSON `attributes` column for
category-specific specs. One Chroma collection for vector search.
Adding a new category is just new rows, never new code.
"""
import json
import logging
import os
from functools import lru_cache
from typing import Optional

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import QueuePool

import config
from TOOLS.product_schema import CORE_REQUIRED, missing_fields
from TOOLS.product_normalizer import normalize_with_llm

logger = logging.getLogger("agentic_salesman.db")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "..", "WORKFLOW", "chroma_db")

PRODUCTS_TABLE = "products"

CORE_COLUMNS = (
    "id", "category", "name", "brand", "price", "mrp", "units_available",
    "rating", "online_link", "offline_availability", "description",
)


def _connection_url() -> URL:
    """Build the MySQL connection URL from config."""
    return URL.create(
        drivername="mysql+pymysql",
        username=config.DB_USERNAME,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
    )


# ── Shared pooled engine (reused across the app) ──────────────────────

_shared_engine = None


def get_shared_engine():
    """Return a long-lived, connection-pooled engine for the app. Safe to
    call from multiple threads — SQLAlchemy's QueuePool handles it."""
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = create_engine(
            _connection_url(),
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,       # recycle connections every 30 min
            pool_pre_ping=True,      # verify connection is alive before use
            connect_args={"connect_timeout": 10},
        )
        logger.info(
            "Created shared DB engine: %s@%s:%s/%s (pool_size=5)",
            config.DB_USERNAME, config.DB_HOST, config.DB_PORT, config.DB_NAME,
        )
    return _shared_engine


def build_engine(timeout_seconds: Optional[int] = None):
    """Short-lived engine for one-off operations (health checks, etc.).
    Callers should .dispose() it in a finally block."""
    connect_args = {"connect_timeout": timeout_seconds} if timeout_seconds else {}
    return create_engine(_connection_url(), connect_args=connect_args)


def list_categories() -> list:
    """Distinct category names from the products table. Returns [] on
    any error — never blocks a chat turn."""
    engine = get_shared_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT DISTINCT category FROM {PRODUCTS_TABLE} ORDER BY category")
            )
            return [row[0] for row in rows if row[0] and str(row[0]).strip()]
    except Exception as exc:
        logger.warning("Failed to list categories: %s", exc)
        return []


def parse_attributes(value) -> dict:
    """Parse the JSON attributes column. Always returns a dict, never raises."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        if isinstance(value, float) and pd.isna(value):
            return {}
    except TypeError:
        pass
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@lru_cache(maxsize=1)
def _get_embeddings():
    """Cache the embedding model so it's loaded once per process."""
    logger.info("Loading embedding model: all-MiniLM-L6-v2")
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


class DB_CONNECTOR:
    """Builds (or reuses) a single Chroma vector store backed by the
    MySQL products table. Sync is by row count — if MySQL and Chroma
    match, nothing is re-embedded; otherwise the collection is rebuilt."""

    def __init__(self):
        self.engine = get_shared_engine()

        self._store = Chroma(
            collection_name="products",
            embedding_function=_get_embeddings(),
            persist_directory=CHROMA_DIR,
        )

        incomplete_log = []
        rebuilt = {"value": False}

        def _document_builder(df):
            rebuilt["value"] = True
            return self._product_documents(
                df, on_incomplete=lambda pid, missing: incomplete_log.append((pid, missing))
            )

        self._sync_table(PRODUCTS_TABLE, self._store, _document_builder)

        # Only re-stamp ingestion_status when _product_documents actually
        # ran this pass (i.e. _sync_table decided to rebuild) -- if the
        # collection was already in sync, _document_builder was never
        # called, and blindly marking every row "complete" here would
        # silently launder any row a *previous* sync had marked
        # incomplete without ever re-checking it.
        if rebuilt["value"]:
            self._record_incomplete(incomplete_log)

        self.categories = self._fetch_categories()

    def _fetch_categories(self) -> list:
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(f"SELECT DISTINCT category FROM {PRODUCTS_TABLE} ORDER BY category")
                )
                return [row[0] for row in rows if row[0] and str(row[0]).strip()]
        except Exception as exc:
            logger.warning("Failed to fetch categories after sync: %s", exc)
            return []

    def _sync_table(self, table_name, store, document_builder):
        df = pd.read_sql(f"SELECT * FROM {table_name}", self.engine)
        existing_ids = store.get(include=[]).get("ids", [])

        if len(existing_ids) == len(df):
            logger.info(
                "Chroma collection '%s' is in sync (%d vectors = %d rows)",
                table_name, len(existing_ids), len(df),
            )
            return

        if existing_ids:
            logger.info(
                "%s: %d vectors vs %d rows — rebuilding collection",
                table_name, len(existing_ids), len(df),
            )
            store.delete(ids=existing_ids)

        documents = document_builder(df)
        if documents:
            store.add_documents(documents)
            logger.info("Embedded %d products into Chroma", len(documents))

    @staticmethod
    def _product_documents(df, on_incomplete=None):
        """Builds one Document per RAG-eligible row.

        A row is RAG-eligible once TOOLS.product_schema.missing_fields
        returns an empty set for it -- name/brand/price plus every
        required field for its category. A row that's missing only
        category-specific (non-core) fields gets one best-effort LLM
        normalization pass (TOOLS.product_normalizer.normalize_with_llm)
        before the gate is re-checked; a row still incomplete after that
        is skipped entirely (never embedded) and reported to
        `on_incomplete(product_id, sorted_missing_fields)` when a caller
        supplied one, so the incomplete status can be written back to
        MySQL (see DB_CONNECTOR._record_incomplete)."""
        documents = []

        for _, row in df.iterrows():
            record = row.to_dict()
            attributes = parse_attributes(record.pop("attributes", None))
            category = record.get("category") or "product"

            combined = {**record, **attributes}
            missing = missing_fields(category, combined)

            attribute_gaps = missing - set(CORE_REQUIRED)
            if attribute_gaps:
                attributes = normalize_with_llm(
                    category,
                    record.get("name", ""),
                    record.get("description", ""),
                    attributes,
                    attribute_gaps,
                )
                combined = {**record, **attributes}
                missing = missing_fields(category, combined)

            if missing:
                logger.warning(
                    "Skipping product %r (id=%s): missing required fields %s",
                    record.get("name"), record.get("id"), sorted(missing),
                )
                if on_incomplete:
                    on_incomplete(record.get("id"), sorted(missing))
                continue

            metadata = {
                key: value
                for key, value in combined.items()
                if value is not None and isinstance(value, (str, int, float, bool))
            }

            name = record.get("name", "")
            brand = record.get("brand", "")
            price = record.get("price", "")
            description = (record.get("description") or "").strip()

            spec_text = ", ".join(
                f"{key}: {value}" for key, value in attributes.items()
                if value not in (None, "")
            )

            feedback = (record.get("customer_feedback") or "").strip()

            page_content = f"{name} is a {brand} {category} priced at ₹{price}."
            if description:
                page_content += f" {description}"
            if spec_text:
                page_content += f" Features: {spec_text}."
            if feedback:
                page_content += f" Customer reviews: {feedback}"

            documents.append(Document(page_content=page_content, metadata=metadata))

        return documents

    def _record_incomplete(self, incomplete_log):
        """Best-effort write-back of ingestion status for rows the gate
        excluded, so catalog_sync_dag.py's verify_collection task can
        assert against "complete" rows instead of the total row count.
        No-ops (with a log line, never a raised exception) on a database
        that hasn't run sql/add_ingestion_status.sql yet -- this is
        bookkeeping, not something that should ever block a sync."""
        try:
            with self.engine.begin() as conn:
                conn.execute(text(f"UPDATE {PRODUCTS_TABLE} SET ingestion_status = 'complete'"))
                for product_id, missing in incomplete_log:
                    conn.execute(
                        text(
                            f"UPDATE {PRODUCTS_TABLE} "
                            f"SET ingestion_status = 'incomplete', "
                            f"ingestion_missing_fields = :missing "
                            f"WHERE id = :id"
                        ),
                        {"missing": json.dumps(missing), "id": product_id},
                    )
            logger.info(
                "Recorded ingestion status: %d product(s) incomplete", len(incomplete_log)
            )
        except Exception as exc:
            logger.warning(
                "Could not record ingestion_status (has sql/add_ingestion_status.sql "
                "been run against this database yet?): %s", exc,
            )

    def vector_database(self):
        return self._store

    def get_categories(self) -> list:
        return list(self.categories)


def check_mysql_connectivity(timeout_seconds: int = 3) -> None:
    """Cheap standalone connectivity check for /api/health. Raises on
    failure; returns None on success."""
    engine = build_engine(timeout_seconds)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()
