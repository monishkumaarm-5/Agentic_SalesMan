import os

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

import config

# Anchor the persisted Chroma directory to this file's location so it always
# resolves to WORKFLOW/chroma_db regardless of the working directory the app
# is launched from (e.g. `uvicorn APP.main:app` run from the repo root).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "..", "WORKFLOW", "chroma_db")


class DB_CONNECTOR:
    """
    Builds (or reuses) three Chroma vector stores -- phone, laptop,
    headphone -- backed by the MySQL retail_shop database.

    Each collection is only embedded from MySQL once: if it already holds
    vectors from a previous run, re-embedding is skipped. Without this check,
    every process restart during development would keep appending duplicate
    documents to the persisted Chroma store.
    """

    def __init__(self):
        connection_url = URL.create(
            drivername="mysql+pymysql",
            username=config.DB_USERNAME,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
        )
        self.engine = create_engine(connection_url)

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
        existing = store.get(include=[])
        if existing and existing.get("ids"):
            return
        df = pd.read_sql(f"SELECT * FROM {table_name}", self.engine)
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
