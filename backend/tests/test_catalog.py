from unittest.mock import MagicMock

import pandas as pd
import pytest
from langchain_core.documents import Document

from app import company
from app.catalog import schema, tools
from app.catalog.database import expand_attributes
from app.catalog.index import CatalogIndex, build_documents, catalog_fingerprint


def raw(rows):
    return pd.DataFrame(rows)


PHONES = [
    {"id": i, "category": "Mobile", "name": f"Phone {i}", "brand": "B", "price": 1000 * i,
     "attributes": '{"ram": "8GB", "battery": "5000mAh"}'} for i in range(1, 5)
]


def test_expected_attributes_are_learned_from_the_data():
    assert schema.expected_attributes([{"ram", "battery"}, {"ram"}, {"ram", "battery"}]) == {"ram", "battery"}
    assert schema.expected_attributes([{"ram"}, {"ram"}]) == set()  # too few rows to judge


def test_build_documents_marks_partial_and_rejects_rows_without_core_fields():
    rows = PHONES + [
        {"id": 9, "category": "Mobile", "name": "Gap Phone", "brand": "B", "price": 5, "attributes": '{"ram": "4GB"}'},
        {"id": 10, "category": "Mobile", "name": None, "brand": "B", "price": 5, "attributes": None},
    ]
    from app.catalog.index import SyncReport

    report = SyncReport()
    docs = build_documents(raw(rows), fill=None, report=report)
    assert len(docs) == 5
    assert report.partial == [(9, ["battery"])]
    assert report.rejected == [(10, ["name"])]
    assert docs[0].metadata["attribute_keys"] == "ram|battery"


def test_missing_attributes_can_be_filled():
    rows = PHONES + [{"id": 9, "category": "Mobile", "name": "Gap", "brand": "B", "price": 5,
                      "attributes": '{"ram": "4GB"}', "description": "4000mAh battery"}]
    fill = MagicMock(side_effect=lambda cat, name, desc, attrs, missing: {**attrs, "battery": "4000mAh"})
    docs = build_documents(raw(rows), fill=fill)
    assert "battery: 4000mAh" in docs[-1].page_content
    fill.assert_called_once()


def test_fingerprint_ignores_bookkeeping():
    a = raw([{"id": 1, "name": "A", "ingestion_status": None}])
    b = raw([{"id": 1, "name": "A", "ingestion_status": "complete"}])
    assert catalog_fingerprint(a) == catalog_fingerprint(b)
    assert catalog_fingerprint(a) != catalog_fingerprint(raw([{"id": 1, "name": "B"}]))


@pytest.fixture
def index(tmp_path, monkeypatch):
    store = MagicMock()
    store.get.return_value = {"ids": []}
    idx = CatalogIndex(store=store, engine=MagicMock(), fill=None, persist_dir=tmp_path)
    monkeypatch.setattr("app.catalog.index.load_raw_products", lambda engine=None: raw(PHONES))
    return idx


def test_sync_indexes_with_stable_ids_then_skips_when_unchanged(index):
    report = index.sync()
    assert report.rebuilt and report.indexed == 4
    ids = index.store.add_documents.call_args.kwargs["ids"]
    assert ids == ["product-1", "product-2", "product-3", "product-4"]

    index.store.reset_mock()
    index.store.get.return_value = {"ids": ids}
    assert not index.sync().rebuilt
    index.store.add_documents.assert_not_called()


def test_sync_rebuilds_when_catalog_changes(index, monkeypatch):
    index.sync()
    index.store.get.return_value = {"ids": ["product-1"]}
    monkeypatch.setattr("app.catalog.index.load_raw_products",
                        lambda engine=None: raw(PHONES[:1] + [{**PHONES[1], "price": 1}]))
    assert index.sync().rebuilt
    index.store.delete.assert_called_with(ids=["product-1"])


def test_search_returns_rows_with_attribute_keys(index):
    index.store.similarity_search_with_relevance_scores.return_value = [
        (Document(page_content="x", metadata={"name": "A", "attribute_keys": "ram|battery"}), 0.8)]
    [(row, score)] = index.search("q", "Mobile", 5)
    assert row["attribute_keys"] == ["ram", "battery"] and score == 0.8
    assert index.store.similarity_search_with_relevance_scores.call_args.kwargs["filter"] == {"category": "Mobile"}


def test_expand_attributes_keeps_core_columns():
    df = expand_attributes(raw([{"id": 1, "name": "A", "attributes": '{"ram": "8GB", "name": "evil"}'}]))
    assert df.loc[0, "name"] == "A" and df.loc[0, "ram"] == "8GB"
    assert df.loc[0, "attribute_keys"] == ["ram"]


LOADED = expand_attributes(raw(PHONES + [{"id": 7, "category": "Laptop", "name": "Book Pro", "brand": "Z",
                                           "price": 90000, "mrp": None, "attributes": '{"ram": "16GB"}'}]))


def loader(category):
    return LOADED if not category else LOADED[LOADED["category"].str.lower() == category.lower()]


def test_search_products_filters():
    assert [p["name"] for p in tools.search_products("mobile", max_price=2500, loader=loader)] == ["Phone 1", "Phone 2"]
    assert tools.search_products(keyword="16gb", loader=loader)[0]["name"] == "Book Pro"
    with pytest.raises(tools.ProductToolError):
        tools.search_products(" ", loader=loader)


def test_compare_products_is_json_safe():
    result = tools.compare_products(["Phone 1", "book pro"], loader=loader)
    assert set(result["products"]) == {"Phone 1", "Book Pro"}
    assert "price" in result["differing_fields"]
    assert result["products"]["Book Pro"]["mrp"] is None
    with pytest.raises(tools.ProductToolError):
        tools.compare_products(["Phone 1", "Nope"], loader=loader)


def test_find_products_fuzzy():
    assert [p["name"] for p in tools.find_products(["phone 3", "Book Pr"], loader=loader)] == ["Phone 3", "Book Pro"]


def test_store_matching():
    assert [s["name"] for s in company.stores_carrying("Available at Trein T Nagar, Koramangala")] == [
        "Trein T Nagar", "Trein Koramangala"]
    assert company.stores_carrying("Available at Croma") == []
    assert company.available_in_city("Available at Trein Koramangala", "bengaluru")
    assert not company.available_in_city("Available at Trein Koramangala", "chennai")
