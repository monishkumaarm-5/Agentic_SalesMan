"""
Tests for TOOLS/product_tools.py. MySQL access goes through
DATABASE.SQL_CONNECTOR.build_engine() + pandas.read_sql, both mocked here --
these tests are about the filtering/matching/comparison logic, not real
database I/O (see tests/test_sql_connector.py for the sync-logic tests).
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from TOOLS import product_tools as pt

LAPTOPS = pd.DataFrame(
    [
        {
            "name": "Lenovo LOQ",
            "brand": "Lenovo",
            "storage": "512GB",
            "ram": "16GB",
            "processor": "i5 RTX 4050",
            "color": "Black",
            "price": 72999,
        },
        {
            "name": "HP Pavilion",
            "brand": "HP",
            "storage": "256GB",
            "ram": "8GB",
            "processor": "i3",
            "color": "Silver",
            "price": 55000,
        },
        {
            "name": "Dell XPS",
            "brand": "Dell",
            "storage": "1TB",
            "ram": "32GB",
            "processor": "i7",
            "color": "Black",
            "price": 150000,
        },
    ]
)


def _patched(df=LAPTOPS):
    return patch("TOOLS.product_tools.pd.read_sql", return_value=df), patch(
        "TOOLS.product_tools.build_engine", return_value=MagicMock()
    )


def test_parse_numeric_handles_common_formats():
    assert pt.parse_numeric(16) == 16
    assert pt.parse_numeric("16GB") == 16
    assert pt.parse_numeric("1TB") == 1000
    assert pt.parse_numeric("₹45,999") == 45999
    assert pt.parse_numeric(None) is None
    assert pt.parse_numeric("no digits here") is None


def test_search_products_rejects_unknown_category():
    with pytest.raises(pt.ProductToolError):
        pt.search_products("tablet")


def test_search_products_filters_by_max_price():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        results = pt.search_products("laptop", max_price=80000)
    names = {r["name"] for r in results}
    assert names == {"Lenovo LOQ", "HP Pavilion"}


def test_search_products_filters_by_min_ram():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        results = pt.search_products("laptop", min_ram_gb=16)
    names = {r["name"] for r in results}
    assert names == {"Lenovo LOQ", "Dell XPS"}


def test_search_products_filters_by_brand_case_insensitively():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        results = pt.search_products("laptop", brand="lenovo")
    assert [r["name"] for r in results] == ["Lenovo LOQ"]


def test_search_products_respects_limit_and_sorts_by_price():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        results = pt.search_products("laptop", limit=2)
    assert [r["name"] for r in results] == ["HP Pavilion", "Lenovo LOQ"]


def test_get_product_details_exact_match():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        details = pt.get_product_details("laptop", "HP Pavilion")
    assert details["brand"] == "HP"


def test_get_product_details_fuzzy_match():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        details = pt.get_product_details("laptop", "hp pavillion")  # typo
    assert details["name"] == "HP Pavilion"


def test_get_product_details_returns_none_when_nothing_matches():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        details = pt.get_product_details("laptop", "Nonexistent Gadget Zeta")
    assert details is None


def test_compare_products_needs_at_least_two_names():
    with pytest.raises(pt.ProductToolError):
        pt.compare_products("laptop", ["Lenovo LOQ"])


def test_compare_products_reports_differences():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        result = pt.compare_products("laptop", ["Lenovo LOQ", "HP Pavilion"])
    assert set(result["products"]) == {"Lenovo LOQ", "HP Pavilion"}
    assert "price" in result["differing_fields"]
    assert result["missing"] == []


def test_compare_products_reports_missing_names():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        with pytest.raises(pt.ProductToolError):
            pt.compare_products("laptop", ["Lenovo LOQ", "Totally Made Up Model"])


def test_check_inventory_defaults_to_catalog_presence_when_no_stock_column():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        result = pt.check_inventory("laptop", "Dell XPS")
    assert result["in_stock"] is True
    assert result["source"] == "catalog-presence"


def test_check_inventory_uses_a_real_stock_column_when_present():
    df = LAPTOPS.copy()
    df["stock"] = [0, 5, 3]
    read_sql_patch, engine_patch = _patched(df)
    with read_sql_patch, engine_patch:
        result = pt.check_inventory("laptop", "Lenovo LOQ")
    assert result["in_stock"] is False
    assert result["quantity"] == 0
    assert result["source"] == "stock"


def test_check_inventory_raises_for_unknown_product():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        with pytest.raises(pt.ProductToolError):
            pt.check_inventory("laptop", "Totally Made Up Model")


def test_get_current_price_returns_the_price_and_currency():
    read_sql_patch, engine_patch = _patched()
    with read_sql_patch, engine_patch:
        result = pt.get_current_price("laptop", "HP Pavilion")
    assert result == {"product": "HP Pavilion", "price": 55000.0, "currency": "INR"}
