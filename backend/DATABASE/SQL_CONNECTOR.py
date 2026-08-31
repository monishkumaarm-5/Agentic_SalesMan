import logging
import os
from typing import Optional

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

import config

logger = logging.getLogger("agentic_salesman.db")

# Anchor the persisted Chroma directory to this file's location so it always
# resolves to WORKFLOW/chroma_db regardless of the working directory the app
# is launched from (e.g. `uvicorn APP.main:app` run from the repo root).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "..", "WORKFLOW", "chroma_db")

# Table names line up 1:1 with the RAG vector store names used elsewhere
# (DB_CONNECTOR.__vector_stores keys / AGENT_FUNCS in ORCHE.py), just
# without the "phone"/"laptop"/"headphone" -> MOBILE/LAPTOP/HEADPHONE label
# translation those layers do.
TABLES = {"phone": "phone", "laptop": "laptop", "headphone": "headphone"}


def build_engine(timeout_seconds: Optional[int] = None):
    """Shared MySQL engine builder. A short-lived engine per call (rather
    than a shared pool) keeps this safe to use from short, occasional
    operations -- health checks, tool calls -- without worrying about
    connection lifetime across threads; callers should `.dispose()` it in a
    finally block when they're done (see check_mysql_connectivity below and
    TOOLS/product_tools.py)."""
    connection_url = URL.create(
        drivername="mysql+pymysql",
        username=config.DB_USERNAME,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
    )
    connect_args = {"connect_timeout": timeout_seconds} if timeout_seconds else {}
    return create_engine(connection_url, connect_args=connect_args)


class DB_CONNECTOR:
    """
    Builds (or reuses) three Chroma vector stores -- phone, laptop,
    headphone -- backed by the MySQL retail_shop database.

    Each collection is synced against its MySQL table by row count: if the
    counts already match, nothing is re-embedded (so a plain process restart
    doesn't keep appending duplicate documents to the persisted Chroma
    store); if they don't match -- new products inserted, or some removed --
    the collection is rebuilt from scratch so the RAG data doesn't quietly
    go stale.
    """

    def __init__(self):
        self.engine = build_engine()

        embedding = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        self.__vector_stores = {
            "phone": Chroma(
                collection_name="phones",
                embedding_function=embedding,
                persist_directory=CHROMA_DIR,
            ),
            "laptop": Chroma(
                collection_name="laptops",
                embedding_function=embedding,
                persist_directory=CHROMA_DIR,
            ),
            "headphone": Chroma(
                collection_name="headphones",
                embedding_function=embedding,
                persist_directory=CHROMA_DIR,
            ),
        }

        self._sync_table("phone", self.__vector_stores["phone"], self._phone_documents)
        self._sync_table("laptop", self.__vector_stores["laptop"], self._laptop_documents)
        self._sync_table("headphone", self.__vector_stores["headphone"], self._headphone_documents)

    def _sync_table(self, table_name, store, document_builder):
        df = pd.read_sql(f"SELECT * FROM {table_name}", self.engine)
        existing_ids = store.get(include=[]).get("ids", [])

        if len(existing_ids) == len(df):
            return

        if existing_ids:
            logger.info(
                "%s collection has %d vectors but MySQL has %d rows -- rebuilding",
                table_name, len(existing_ids), len(df),
            )
            store.delete(ids=existing_ids)

        documents = document_builder(df)
        if documents:
            store.add_documents(documents)

    @staticmethod
    def _phone_documents(df):
        documents = []
        for _, row in df.iterrows():
            documents.append(
                Document(
                    page_content=(
                        f"{row['name']} is a {row['brand']} smartphone with "
                        f"{row['storage']} storage, {row['ram']} RAM, "
                        f"{row['processor']} processor, available in {row['color']} color. "
                        f"It costs ₹{row['price']}."
                    ),
                    metadata=row.to_dict(),
                )
            )
        return documents

    @staticmethod
    def _laptop_documents(df):
        documents = []
        for _, row in df.iterrows():
            documents.append(
                Document(
                    page_content=(
                        f"{row['name']} is a {row['brand']} laptop with "
                        f"{row['storage']} storage, {row['ram']} RAM, "
                        f"powered by a {row['processor']} processor, "
                        f"available in {row['color']} color. "
                        f"It costs ₹{row['price']}."
                    ),
                    metadata=row.to_dict(),
                )
            )
        return documents

    @staticmethod
    def _headphone_documents(df):
        documents = []
        for _, row in df.iterrows():
            documents.append(
                Document(
                    page_content=(
                        f"{row['name']} is a {row['brand']} {row['type']} headphone. "
                        f"It comes in {row['color']} color and offers {row['quality']} sound quality. "
                        f"It costs ₹{row['price']}."
                    ),
                    metadata=row.to_dict(),
                )
            )
        return documents

    def phone_vector_database(self):
        return self.__vector_stores["phone"]

    def laptop_vector_database(self):
        return self.__vector_stores["laptop"]

    def headphone_vector_database(self):
        return self.__vector_stores["headphone"]


def check_mysql_connectivity(timeout_seconds: int = 3) -> None:
    """Cheap standalone connectivity check for /api/health. Deliberately
    does not build a full DB_CONNECTOR (that also loads the embedding model
    and touches Chroma, both too slow for a health check that might be
    polled every few seconds). Raises on failure; returns None on success."""
    engine = build_engine(timeout_seconds)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()
