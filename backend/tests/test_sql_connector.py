"""
Tests for DATABASE/SQL_CONNECTOR.py's sync logic. DB_CONNECTOR.__init__
touches real MySQL/Chroma/embeddings, so these tests exercise `_sync_table`
and the document builders directly on a bare instance instead of going
through __init__.
"""
from unittest.mock import MagicMock, patch

import pandas as pd

from DATABASE.SQL_CONNECTOR import DB_CONNECTOR, check_mysql_connectivity


def _bare_connector():
    connector = DB_CONNECTOR.__new__(DB_CONNECTOR)
    connector.engine = MagicMock()
    return connector


def test_sync_table_skips_when_counts_already_match():
    df = pd.DataFrame([{"name": "A"}, {"name": "B"}])
    connector = _bare_connector()
    store = MagicMock()
    store.get.return_value = {"ids": ["1", "2"]}

    with patch("DATABASE.SQL_CONNECTOR.pd.read_sql", return_value=df):
        connector._sync_table("phone", store, lambda d: ["doc"] * len(d))

    store.delete.assert_not_called()
    store.add_documents.assert_not_called()


def test_sync_table_embeds_when_collection_is_empty():
    df = pd.DataFrame([{"name": "A"}])
    connector = _bare_connector()
    store = MagicMock()
    store.get.return_value = {"ids": []}
    built = ["doc1"]

    with patch("DATABASE.SQL_CONNECTOR.pd.read_sql", return_value=df):
        connector._sync_table("phone", store, lambda d: built)

    store.delete.assert_not_called()
    store.add_documents.assert_called_once_with(built)


def test_sync_table_rebuilds_on_count_mismatch():
    """Regression test: products added to MySQL after the first embedding
    pass used to never show up in the vector store."""
    df = pd.DataFrame([{"name": "A"}, {"name": "B"}, {"name": "C"}])
    connector = _bare_connector()
    store = MagicMock()
    store.get.return_value = {"ids": ["1", "2"]}  # stale: only 2, MySQL has 3
    built = ["doc1", "doc2", "doc3"]

    with patch("DATABASE.SQL_CONNECTOR.pd.read_sql", return_value=df):
        connector._sync_table("phone", store, lambda d: built)

    store.delete.assert_called_once_with(ids=["1", "2"])
    store.add_documents.assert_called_once_with(built)


def test_check_mysql_connectivity_runs_select_1_and_disposes():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("DATABASE.SQL_CONNECTOR.create_engine", return_value=mock_engine):
        check_mysql_connectivity()  # should not raise

    assert mock_conn.execute.called
    assert mock_engine.dispose.called


def test_check_mysql_connectivity_propagates_failure():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("connection refused")

    with patch("DATABASE.SQL_CONNECTOR.create_engine", return_value=mock_engine):
        try:
            check_mysql_connectivity()
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError to propagate")

    assert mock_engine.dispose.called


def test_phone_documents_render_expected_fields():
    df = pd.DataFrame(
        [
            {
                "name": "iPhone 14",
                "brand": "Apple",
                "storage": "128GB",
                "ram": "6GB",
                "processor": "A15 Bionic",
                "color": "Midnight",
                "price": 699.0,
            }
        ]
    )
    docs = DB_CONNECTOR._phone_documents(df)
    assert len(docs) == 1
    assert "iPhone 14" in docs[0].page_content
    assert "Apple" in docs[0].page_content
    assert docs[0].metadata["name"] == "iPhone 14"


def test_headphone_documents_render_expected_fields():
    df = pd.DataFrame(
        [
            {
                "name": "SoundMax 200",
                "brand": "Acme",
                "type": "over-ear",
                "color": "Black",
                "quality": "Hi-Fi",
                "price": 79.0,
            }
        ]
    )
    docs = DB_CONNECTOR._headphone_documents(df)
    assert len(docs) == 1
    assert "SoundMax 200" in docs[0].page_content
    assert "over-ear" in docs[0].page_content
