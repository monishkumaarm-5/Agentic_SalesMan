"""
Tests for DATABASE/SQL_CONNECTOR.py's sync logic and generic document
builder. DB_CONNECTOR.__init__ touches real MySQL/Chroma/embeddings, so
these tests exercise `_sync_table`/`_product_documents`/`list_categories`
directly on a bare instance instead of going through __init__.

`_product_documents` now gates each row through
TOOLS.product_schema.missing_fields (a product missing a required field
for its category is never embedded) with a best-effort
TOOLS.product_normalizer.normalize_with_llm fallback first -- see the
"gate"/"normalizer" tests below. Both are patched out in tests that
don't care about that behaviour, so they stay hermetic (no real LLM
calls) and unaffected by the gate.
"""
import json
from unittest.mock import MagicMock, patch

import pandas as pd

from DATABASE.SQL_CONNECTOR import (
    DB_CONNECTOR,
    check_mysql_connectivity,
    list_categories,
    parse_attributes,
)


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
        connector._sync_table("products", store, lambda d: ["doc"] * len(d))

    store.delete.assert_not_called()
    store.add_documents.assert_not_called()


def test_sync_table_embeds_when_collection_is_empty():
    df = pd.DataFrame([{"name": "A"}])
    connector = _bare_connector()
    store = MagicMock()
    store.get.return_value = {"ids": []}
    built = ["doc1"]

    with patch("DATABASE.SQL_CONNECTOR.pd.read_sql", return_value=df):
        connector._sync_table("products", store, lambda d: built)

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
        connector._sync_table("products", store, lambda d: built)

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


def test_parse_attributes_handles_json_string_dict_and_none():
    assert parse_attributes('{"ram": "8GB"}') == {"ram": "8GB"}
    assert parse_attributes({"ram": "8GB"}) == {"ram": "8GB"}
    assert parse_attributes(None) == {}
    assert parse_attributes("not json") == {}
    assert parse_attributes("") == {}
    assert parse_attributes("[1, 2, 3]") == {}  # valid JSON, but not an object


def test_product_documents_render_expected_fields_and_flatten_attributes():
    df = pd.DataFrame(
        [
            {
                "name": "iPhone 15",
                "brand": "Apple",
                "category": "Mobile",
                "price": 69999,
                "description": "",
                "attributes": json.dumps(
                    {"ram": "6GB", "storage": "128GB", "battery": "3349mAh"}
                ),
            }
        ]
    )
    docs = DB_CONNECTOR._product_documents(df)
    assert len(docs) == 1
    assert "iPhone 15" in docs[0].page_content
    assert "Apple" in docs[0].page_content
    assert "ram: 6GB" in docs[0].page_content
    assert docs[0].metadata["name"] == "iPhone 15"
    assert docs[0].metadata["ram"] == "6GB"
    assert docs[0].metadata["storage"] == "128GB"
    assert "attributes" not in docs[0].metadata


def test_product_documents_handle_missing_attributes_and_description_gracefully():
    df = pd.DataFrame(
        [{"name": "Trein Fan", "brand": "Havells", "category": "Fan", "price": 1999, "description": None}]
    )
    docs = DB_CONNECTOR._product_documents(df)
    assert len(docs) == 1
    assert "Trein Fan" in docs[0].page_content
    assert docs[0].metadata["name"] == "Trein Fan"


def test_list_categories_returns_distinct_values():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value = [("Laptop",), ("Mobile",)]
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("DATABASE.SQL_CONNECTOR.create_engine", return_value=mock_engine):
        categories = list_categories()

    assert categories == ["Laptop", "Mobile"]
    assert mock_engine.dispose.called


def test_list_categories_fails_open_to_empty_list_on_error():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("db down")

    with patch("DATABASE.SQL_CONNECTOR.create_engine", return_value=mock_engine):
        assert list_categories() == []


def test_get_categories_returns_a_copy_not_a_reference():
    connector = _bare_connector()
    connector.categories = ["Mobile", "Laptop"]

    result = connector.get_categories()
    result.append("Should not leak back")

    assert connector.categories == ["Mobile", "Laptop"]


def test_product_documents_skips_a_row_missing_required_fields():
    """A Mobile row missing `battery` (required -- TOOLS/product_schema.py)
    is never embedded, even though ram/storage are present. The
    normalizer is patched to a no-op so this stays a pure gate test."""
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "name": "No Battery Phone",
                "brand": "Acme",
                "category": "Mobile",
                "price": 9999,
                "description": "",
                "attributes": json.dumps({"ram": "4GB", "storage": "64GB"}),
            }
        ]
    )
    with patch(
        "DATABASE.SQL_CONNECTOR.normalize_with_llm",
        side_effect=lambda category, name, description, attributes, missing: attributes,
    ) as mock_normalize:
        docs = DB_CONNECTOR._product_documents(df)

    assert docs == []
    mock_normalize.assert_called_once()
    # only the non-core gap (battery) is ever handed to the normalizer --
    # name/brand/price are already present, so they're not attribute gaps
    assert mock_normalize.call_args.args[4] == {"battery"}


def test_product_documents_reports_incomplete_rows_via_on_incomplete():
    df = pd.DataFrame(
        [
            {
                "id": 42,
                "name": "No Battery Phone",
                "brand": "Acme",
                "category": "Mobile",
                "price": 9999,
                "description": "",
                "attributes": json.dumps({"ram": "4GB", "storage": "64GB"}),
            }
        ]
    )
    reports = []
    with patch(
        "DATABASE.SQL_CONNECTOR.normalize_with_llm",
        side_effect=lambda category, name, description, attributes, missing: attributes,
    ):
        DB_CONNECTOR._product_documents(df, on_incomplete=lambda pid, missing: reports.append((pid, missing)))

    assert reports == [(42, ["battery"])]


def test_product_documents_embeds_a_row_the_normalizer_completes():
    """When normalize_with_llm successfully fills the gap, the row passes
    the gate on the second check and gets embedded."""
    df = pd.DataFrame(
        [
            {
                "id": 2,
                "name": "Mystery Phone",
                "brand": "Acme",
                "category": "Mobile",
                "price": 14999,
                "description": "A phone with a 5000mAh battery.",
                "attributes": json.dumps({"ram": "6GB", "storage": "128GB"}),
            }
        ]
    )

    def _fill_battery(category, name, description, attributes, missing):
        assert missing == {"battery"}
        return {**attributes, "battery": "5000mAh"}

    with patch("DATABASE.SQL_CONNECTOR.normalize_with_llm", side_effect=_fill_battery):
        docs = DB_CONNECTOR._product_documents(df)

    assert len(docs) == 1
    assert docs[0].metadata["battery"] == "5000mAh"
    assert "battery: 5000mAh" in docs[0].page_content


def test_product_documents_never_calls_normalizer_when_nothing_is_missing():
    df = pd.DataFrame(
        [{"name": "Trein Fan", "brand": "Havells", "category": "Fan", "price": 1999, "description": None}]
    )
    with patch("DATABASE.SQL_CONNECTOR.normalize_with_llm") as mock_normalize:
        docs = DB_CONNECTOR._product_documents(df)

    assert len(docs) == 1
    mock_normalize.assert_not_called()


def test_record_incomplete_marks_all_complete_then_overwrites_incomplete_ones():
    connector = _bare_connector()
    conn = MagicMock()
    connector.engine.begin.return_value.__enter__.return_value = conn

    connector._record_incomplete([(7, ["battery"])])

    executed = [call.args[0].text if hasattr(call.args[0], "text") else str(call.args[0]) for call in conn.execute.call_args_list]
    assert any("SET ingestion_status = 'complete'" in q for q in executed)
    assert any("SET ingestion_status = 'incomplete'" in q for q in executed)


def test_record_incomplete_fails_open_when_columns_do_not_exist_yet():
    connector = _bare_connector()
    connector.engine.begin.side_effect = RuntimeError("Unknown column 'ingestion_status'")

    connector._record_incomplete([])  # should not raise
