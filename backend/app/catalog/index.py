"""
Semantic index of the catalog (Chroma + a local sentence-transformer).

Sync is by content fingerprint: the index is rebuilt only when a product
row was added, removed or edited since the last sync, and each product is
stored under a stable id (`product-<id>`) so it is never duplicated.
"""
import hashlib
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd
from langchain_core.documents import Document
from sqlalchemy import text

from app.catalog import schema
from app.catalog.database import (
    BOOKKEEPING_COLUMNS,
    PRODUCTS_TABLE,
    expand_attributes,
    get_engine,
    load_raw_products,
)
from app.catalog.utils import is_missing, parse_attributes
from app.core.config import get_settings

logger = logging.getLogger("salesman.catalog.index")

COLLECTION = "products"
ATTRIBUTE_KEYS_FIELD = "attribute_keys"

FillFn = Callable[[str, str, str, dict, set], dict]


@dataclass
class SyncReport:
    rebuilt: bool = False
    indexed: int = 0
    partial: list = field(default_factory=list)   # [(id, missing_attrs)]
    rejected: list = field(default_factory=list)  # [(id, missing_core)]


def catalog_fingerprint(df: pd.DataFrame) -> str:
    """Stable hash of the product rows, ignoring sync bookkeeping columns."""
    stable = df.drop(columns=[c for c in BOOKKEEPING_COLUMNS if c in df.columns])
    stable = stable.reindex(sorted(stable.columns), axis=1)
    if "id" in stable.columns:
        stable = stable.sort_values("id", kind="stable")
    payload = stable.to_json(orient="records", date_format="iso", default_handler=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings

    model = get_settings().embedding_model
    logger.info("Loading embedding model %s", model)
    return HuggingFaceEmbeddings(model_name=model)


def _default_store(persist_dir: Path):
    from langchain_chroma import Chroma

    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(collection_name=COLLECTION, embedding_function=_embeddings(),
                  persist_directory=str(persist_dir))


def _default_fill() -> FillFn | None:
    s = get_settings()
    if not (s.normalize_catalog_with_llm and s.llm_configured):
        return None
    from app.catalog.normalizer import fill_missing_attributes

    return fill_missing_attributes


def build_documents(df: pd.DataFrame, fill: FillFn | None = None, report: SyncReport | None = None) -> list:
    """One Document per indexable product row (raw `products` rows, JSON
    attributes still in the `attributes` column)."""
    report = report or SyncReport()
    if df.empty:
        return []

    attrs_by_row = [parse_attributes(v) for v in (df["attributes"] if "attributes" in df.columns else [None] * len(df))]
    categories = df["category"].fillna("").astype(str).str.strip().str.lower() if "category" in df.columns else pd.Series([""] * len(df))

    expected_by_category = {
        cat: schema.expected_attributes(
            [k for k, v in attrs_by_row[i].items() if not is_missing(v)]
            for i in range(len(df)) if categories.iloc[i] == cat
        )
        for cat in set(categories)
    }

    documents = []
    for position, (_, row) in enumerate(df.iterrows()):
        record = {k: v for k, v in row.to_dict().items() if k != "attributes" and k not in BOOKKEEPING_COLUMNS}
        attributes = attrs_by_row[position]
        product_id = record.get("id")

        core_missing = schema.missing_core(record)
        if core_missing:
            report.rejected.append((product_id, core_missing))
            logger.warning("Not indexing product id=%s: missing %s", product_id, core_missing)
            continue

        gaps = schema.missing_expected(attributes, expected_by_category.get(categories.iloc[position], set()))
        if gaps and fill:
            attributes = fill(str(record.get("category")), str(record.get("name") or ""),
                              str(record.get("description") or ""), attributes, gaps)
            gaps = schema.missing_expected(attributes, gaps)
        if gaps:
            report.partial.append((product_id, sorted(gaps)))

        documents.append(_document(record, attributes))

    report.indexed = len(documents)
    return documents


def _document(record: dict, attributes: dict) -> Document:
    attributes = {k: v for k, v in attributes.items() if not is_missing(v) and k not in record}
    combined = {**record, **attributes}
    metadata = {
        key: value for key, value in combined.items()
        if isinstance(value, (str, int, float, bool)) and not is_missing(value)
    }
    metadata[ATTRIBUTE_KEYS_FIELD] = "|".join(attributes)

    name, brand, category = record.get("name"), record.get("brand") or "", record.get("category")
    parts = [f"{name} is a {brand} {category} priced at {record.get('price')}."]
    if not is_missing(record.get("description")):
        parts.append(str(record["description"]).strip())
    if attributes:
        parts.append("Specs: " + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in attributes.items()) + ".")
    if not is_missing(record.get("customer_feedback")):
        parts.append(f"Customer reviews: {str(record['customer_feedback']).strip()[:600]}")
    return Document(page_content=" ".join(parts), metadata=metadata)


def _document_ids(documents: list) -> list | None:
    ids = []
    for doc in documents:
        product_id = (getattr(doc, "metadata", None) or {}).get("id")
        if product_id is None:
            return None
        ids.append(f"product-{product_id}")
    return ids if len(set(ids)) == len(ids) else None


class CatalogIndex:
    def __init__(self, store=None, engine=None, fill: FillFn | None = ..., persist_dir: Path | None = None):
        settings = get_settings()
        self.persist_dir = Path(persist_dir or settings.chroma_dir)
        self._store = store
        self._engine = engine
        self._fill = _default_fill() if fill is ... else fill
        self._lock = threading.Lock()

    @property
    def store(self):
        if self._store is None:
            self._store = _default_store(self.persist_dir)
        return self._store

    @property
    def engine(self):
        return self._engine or get_engine()

    @property
    def _fingerprint_file(self) -> Path:
        return self.persist_dir / f"{COLLECTION}.fingerprint"

    def _stored_fingerprint(self) -> str | None:
        try:
            return self._fingerprint_file.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def _save_fingerprint(self, value: str) -> None:
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._fingerprint_file.write_text(value, encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save catalog fingerprint: %s", exc)

    def sync(self, force: bool = False) -> SyncReport:
        with self._lock:
            df = load_raw_products(engine=self.engine)
            fingerprint = catalog_fingerprint(df)
            existing = self.store.get(include=[]).get("ids", [])
            report = SyncReport()

            if existing and not force and self._stored_fingerprint() == fingerprint:
                report.indexed = len(existing)
                logger.info("Catalog index up to date (%d products)", len(existing))
                return report

            if existing:
                self.store.delete(ids=existing)
            documents = build_documents(df, self._fill, report)
            if documents:
                ids = _document_ids(documents)
                if ids:
                    self.store.add_documents(documents, ids=ids)
                else:
                    self.store.add_documents(documents)
            report.rebuilt = True
            self._save_fingerprint(fingerprint)
            self._record_status(report)
            logger.info("Indexed %d products (%d partial, %d rejected)",
                        report.indexed, len(report.partial), len(report.rejected))
            return report

    def _record_status(self, report: SyncReport) -> None:
        """Best-effort write-back of per-row ingestion status (needs
        sql/add_ingestion_status.sql). Never raises."""
        try:
            with self.engine.begin() as conn:
                conn.execute(text(f"UPDATE {PRODUCTS_TABLE} SET ingestion_status = 'complete', ingestion_missing_fields = NULL"))
                for status, rows in (("partial", report.partial), ("rejected", report.rejected)):
                    for product_id, missing in rows:
                        conn.execute(
                            text(f"UPDATE {PRODUCTS_TABLE} SET ingestion_status = :s, "
                                 f"ingestion_missing_fields = :m WHERE id = :id"),
                            {"s": status, "m": json.dumps(missing), "id": product_id},
                        )
        except Exception as exc:  # noqa: BLE001
            logger.info("Ingestion status not recorded (%s)", exc)

    def search(self, query: str, category: str | None, k: int) -> list[tuple[dict, float]]:
        """[(product_row, relevance 0..1)] best first."""
        kwargs = {"filter": {"category": category}} if category else {}
        try:
            pairs = self.store.similarity_search_with_relevance_scores(query, k=k, **kwargs)
            hits = [(doc, max(0.0, min(1.0, float(score)))) for doc, score in pairs]
        except Exception as exc:  # noqa: BLE001 - some stores lack relevance scores
            logger.debug("Relevance scores unavailable (%s); using rank order", exc)
            docs = self.store.similarity_search(query, k=k, **kwargs)
            hits = [(doc, 1.0 - i / max(len(docs), 1)) for i, doc in enumerate(docs)]
        return [(_row_from_document(doc), score) for doc, score in hits]


def _row_from_document(doc) -> dict:
    row = dict(doc.metadata or {})
    keys = row.pop(ATTRIBUTE_KEYS_FIELD, "")
    row[ATTRIBUTE_KEYS_FIELD] = [k for k in str(keys).split("|") if k]
    return row


def rows_from_dataframe(df: pd.DataFrame) -> list[dict]:
    """Product rows straight from MySQL in the same shape search() returns
    (used as a fallback when the vector index is unavailable)."""
    from app.catalog.utils import clean_record

    expanded = expand_attributes(df)
    rows = []
    for record in expanded.to_dict(orient="records"):
        record = {k: v for k, v in clean_record(record).items() if k not in BOOKKEEPING_COLUMNS and v is not None}
        rows.append(record)
    return rows
