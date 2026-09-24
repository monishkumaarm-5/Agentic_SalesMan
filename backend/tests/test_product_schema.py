"""
Tests for TOOLS/product_schema.py -- the minimal per-category required-
field list and the missing_fields() ingestion gate that
DATABASE/SQL_CONNECTOR.py's _product_documents calls before embedding a
row into Chroma.
"""
from TOOLS.product_schema import (
    CORE_REQUIRED,
    missing_fields,
    required_fields_for,
)


def test_core_required_fields_apply_to_every_category():
    assert missing_fields("Mobile", {}) == set(CORE_REQUIRED) | {"ram", "storage", "battery"}


def test_a_fully_specified_mobile_has_no_missing_fields():
    record = {"name": "X", "brand": "Y", "price": 999, "ram": "8GB", "storage": "128GB", "battery": "5000mAh"}
    assert missing_fields("Mobile", record) == set()


def test_missing_one_category_specific_field_is_reported():
    record = {"name": "X", "brand": "Y", "price": 999, "ram": "8GB", "storage": "128GB"}
    assert missing_fields("Mobile", record) == {"battery"}


def test_category_matching_is_case_and_whitespace_insensitive():
    record = {"name": "X", "brand": "Y", "price": 999, "capacity": "1.5 Ton", "star_rating": "3 Star", "inverter": "Yes"}
    assert missing_fields("air conditioner", record) == set()
    assert missing_fields("AIR_CONDITIONER", record) == set()
    assert missing_fields("Air Conditioner", record) == set()


def test_unmapped_category_only_needs_core_fields():
    """A brand-new category nobody has taught this module about yet is
    never blocked just for being unrecognized -- only the universal
    name/brand/price fields are checked."""
    assert required_fields_for("Trampoline") == set()
    assert missing_fields("Trampoline", {"name": "X", "brand": "Y", "price": 1}) == set()
    assert missing_fields("Trampoline", {"name": "X"}) == {"brand", "price"}


def test_display_and_screen_size_are_interchangeable_aliases():
    record = {
        "name": "X", "brand": "Y", "price": 999,
        "processor": "Z", "ram": "8GB", "storage": "256GB",
        "screen_size": "15.6-inch",  # not "display", but should still count
    }
    assert missing_fields("Laptop", record) == set()


def test_empty_string_counts_as_missing_not_just_none():
    record = {"name": "", "brand": "Y", "price": 999}
    assert "name" in missing_fields("Trampoline", record)
