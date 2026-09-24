"""
Tests for TOOLS/product_normalizer.py -- the ingestion-time LLM fallback
that DATABASE/SQL_CONNECTOR.py's _product_documents calls for a row that
failed TOOLS.product_schema.missing_fields. The LLM call itself
(_call_llm) is mocked throughout, same pattern as
tests/test_requirement_extractor.py.
"""
from unittest.mock import MagicMock, patch

from TOOLS.product_normalizer import normalize_with_llm


def _result(**fields):
    mock = MagicMock()
    mock.model_dump.return_value = fields
    return mock


def test_returns_attributes_unchanged_when_nothing_is_missing():
    attrs = {"ram": "8GB"}
    assert normalize_with_llm("Mobile", "X", "desc", attrs, set()) is attrs


def test_merges_confidently_extracted_fields_into_a_new_dict():
    original = {"ram": "8GB"}
    with patch(
        "TOOLS.product_normalizer._call_llm",
        return_value=_result(battery="5000mAh"),
    ):
        result = normalize_with_llm("Mobile", "X", "has a 5000mAh battery", original, {"battery"})

    assert result == {"ram": "8GB", "battery": "5000mAh"}
    assert original == {"ram": "8GB"}  # never mutated


def test_drops_null_and_empty_extracted_values():
    with patch(
        "TOOLS.product_normalizer._call_llm",
        return_value=_result(battery=None, storage=""),
    ):
        result = normalize_with_llm("Mobile", "X", "", {}, {"battery", "storage"})

    assert result == {}


def test_never_overwrites_an_attribute_that_was_already_present():
    with patch(
        "TOOLS.product_normalizer._call_llm",
        return_value=_result(ram="16GB"),  # LLM guesses differently
    ):
        result = normalize_with_llm("Mobile", "X", "", {"ram": "8GB"}, {"ram"})

    assert result["ram"] == "8GB"


def test_fails_open_and_leaves_attributes_untouched_on_llm_error():
    original = {"ram": "8GB"}
    with patch("TOOLS.product_normalizer._call_llm", side_effect=RuntimeError("timeout")):
        result = normalize_with_llm("Mobile", "X", "desc", original, {"battery"})

    assert result is original
