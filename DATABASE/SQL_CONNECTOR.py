from sqlalchemy import create_engine
from sqlalchemy.engine import URL
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import config

class DB_CONNECTOR:
    def __init__(self):

        connection_url = URL.create(
            drivername="mysql+pymysql",
            username=config.DB_USERNAME,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME
        )
        self.engine = create_engine(connection_url)
        embedding = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.__vector_stores = {
            "phone": Chroma(
                collection_name="phones",
                embedding_function=embedding,
                persist_directory="./chroma_db"
            ),
            "laptop": Chroma(
                collection_name="laptops",
                embedding_function=embedding,
                persist_directory="./chroma_db"
            ),
            "headphone": Chroma(
                collection_name="headphones",
                embedding_function=embedding,
                persist_directory="./chroma_db"
            )
        }
        #--------------------------------------------------------------#
        df_phone = pd.read_sql("SELECT * FROM phone", self.engine)
        documents_phone = []
        for _, row in df_phone.iterrows():
            document = Document(
                page_content=(
                    f"{row['name']} is a {row['brand']} smartphone with "
                    f"{row['storage']} storage, {row['ram']} RAM, "
                    f"{row['processor']} processor, available in {row['color']} color. "
                    f"It costs ₹{row['price']}."
                ),
                metadata=row.to_dict()
            )
            documents_phone.append(document)
        self.__vector_stores["phone"].add_documents(documents_phone)
        #--------------------------------------------------------------#
        df_laptop = pd.read_sql("SELECT * FROM laptop", self.engine)
        doucument_laptop = []
        for _, row in df_laptop.iterrows():
            document = Document(
                page_content=(
                    f"{row['name']} is a {row['brand']} laptop with "
                    f"{row['storage']} storage, {row['ram']} RAM, "
                    f"powered by a {row['processor']} processor, "
                    f"available in {row['color']} color. "
                    f"It costs ₹{row['price']}."
                ),
                metadata=row.to_dict()
            )

            doucument_laptop.append(document)
        self.__vector_stores["laptop"].add_documents(doucument_laptop)
        # --------------------------------------------------------------#
        df_headphone = pd.read_sql("SELECT * FROM headphone", self.engine)
        documents_headphone = []
        for _, row in df_headphone.iterrows():
            document = Document(
                page_content=(
                    f"{row['name']} is a {row['brand']} {row['type']} headphone. "
                    f"It comes in {row['color']} color and offers {row['quality']} sound quality. "
                    f"It costs ₹{row['price']}."
                ),
                metadata=row.to_dict()
            )
            documents_headphone.append(document)
        self.__vector_stores["headphone"].add_documents(documents_headphone)
        # --------------------------------------------------------------#
    def phone_vector_database(self):
           return self.__vector_stores["phone"]
    def laptop_vector_database(self):
           return self.__vector_stores["laptop"]
    def headphone_vector_database(self):
           return self.__vector_stores["headphone"]