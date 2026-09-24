"""
Tests for TOOLS/product_tools.py. MySQL access goes through
DATABASE.SQL_CONNECTOR.build_engine() + pandas.read_sql, both mocked here --
these tests are about the filtering/matching/comparison logic, not real
database I/O (see tests/test_sql_connector.py for the sync-logic tests).

The catalog is now one generic `products` table with a `category` column
and a JSON `attributes` column (see DATABASE/SQL_CONNECTOR.py and
TOOLS/product_tools._expand_attributes), so these fixtures mirror
`_load_table`'s output -- i.e. `LAPTOPS` already has `ram`/`storage`
flattened to top-level columns, exactly like `_expand_attributes` would
produce from an `attributes` JSON blob.
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


def test_search_products_rejects_blank_category():
    # Categories are data-driven now (whatever's in the `products` table),
    # not a fixed enum -- so a category simply not existing yet is no
    # longer a caller error (it just yields an empty result, see
    # test_search_products_returns_empty_list_for_unknown_category below).
    # The only remaining caller error is a blank category.
    with pytest.raises(pt.ProductToolError):
        pt.search_products("")
    with pytest.raises(pt.ProductToolError):
        pt.search_products("   ")


def test_search_products_returns_empty_list_for_unknown_category():
    read_sql_patch, engine_patch = _patched(pd.DataFrame())
    with read_sql_patch, engine_patch:
        results = pt.search_products("tablet")
    assert results == []


def test_search_products_passes_category_filter_to_the_query():
    mock_read_sql = MagicMock(return_value=LAPTOPS)
    with patch("TOOLS.product_tools.pd.read_sql", mock_read_sql), patch(
        "TOOLS.product_tools.build_engine", return_value=MagicMock()
    ):
        pt.search_products("Laptop")

    assert mock_read_sql.call_count == 1
    _, kwargs = mock_read_sql.call_args
    assert kwargs["params"] == {"category": "Laptop"}


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


# ---------------------------------------------------------------------------
# _expand_attributes -- JSON `attributes` column flattening
# ---------------------------------------------------------------------------
def test_expand_attributes_flattens_json_column_into_top_level_columns():
    df = pd.DataFrame(
        [
            {
                "name": "Trein Cool 200",
                "category": "Refrigerator",
                "price": 24999,
                "attributes": '{"capacity": "200L", "star_rating": "3 Star"}',
            }
        ]
    )
    expanded = pt._expand_attributes(df)
    assert "attributes" not in expanded.columns
    assert expanded.loc[0, "capacity"] == "200L"
    assert expanded.loc[0, "star_rating"] == "3 Star"


def test_expand_attributes_core_column_wins_on_collision():
    # `price` is a core column; if a malformed `attributes` blob also has a
    # `price` key, the real core column must win, not the attribute.
    df = pd.DataFrame(
        [
            {
                "name": "Trein Cool 200",
                "price": 24999,
                "attributes": '{"price": "wrong", "capacity": "200L"}',
            }
        ]
    )
    expanded = pt._expand_attributes(df)
    assert expanded.loc[0, "price"] == 24999
    assert expanded.loc[0, "capacity"] == "200L"


def test_expand_attributes_is_a_no_op_when_no_attributes_column():
    expanded = pt._expand_attributes(LAPTOPS)
    pd.testing.assert_frame_equal(expanded, LAPTOPS)


# ---------------------------------------------------------------------------
# list_categories_tool
# ---------------------------------------------------------------------------
def test_list_categories_tool_delegates_and_limits():
    with patch(
        "DATABASE.SQL_CONNECTOR.list_categories",
        return_value=["Mobile", "Laptop", "Headphone", "Television", "Refrigerator"],
    ):
        assert pt.list_categories_tool(limit=2) == ["Mobile", "Laptop"]
        assert pt.list_categories_tool() == [
            "Mobile", "Laptop", "Headphone", "Television", "Refrigerator",
        ]
