"""
Regression tests for logic bugs fixed during the code audit. Each test
names the bug it pins down.
"""
import math

import pandas as pd
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from AGENTS.GUARDRAIL_AGENT import detect_categories, entry_check
from APP.rate_limit import RateLimitMiddleware
from TOOLS.product_tools import _clean_record, parse_numeric
from WORKFLOW import ORCHE
from WORKFLOW.recommendations import build_buy_info, build_top_picks
from WORKFLOW.scoring import budget_fit_score

CATEGORIES = ["Mobile", "Laptop", "Headphone", "Air Conditioner", "Washing Machine", "Television"]


# --- Guardrail -------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "hey can you recommend a laptop under 50000",
        "hi, I need a phone with a good camera",
        "hello I want to buy a fridge",
    ],
)
def test_greeting_prefix_does_not_swallow_a_real_request(message):
    assert entry_check(message, CATEGORIES)["is_greeting"] is False


@pytest.mark.parametrize("message", ["hi", "Hello there!", "thanks a lot", "good morning", "hi, good evening"])
def test_pure_greetings_are_still_greetings(message):
    assert entry_check(message, CATEGORIES)["is_greeting"] is True


@pytest.mark.parametrize(
    "message, expected",
    [
        ("best noise cancelling headphones", ["Headphone"]),  # "phone" inside "headphones"
        ("do you have it in black?", []),                    # "ac" inside "black"
        ("tell me about each option", []),                   # "ac" inside "each"
        ("is there a dishwasher?", []),                      # "washer" inside "dishwasher"
        ("a split AC for my bedroom", ["Air Conditioner"]),
        ("two laptops for my kids", ["Laptop"]),
        ("washing machines under 30000", ["Washing Machine"]),
    ],
)
def test_category_detection_matches_whole_words_only(message, expected):
    assert detect_categories(message, CATEGORIES) == expected


# --- Scoring ---------------------------------------------------------------

def test_zero_budget_does_not_divide_by_zero():
    assert budget_fit_score(20000, 0) == pytest.approx(0.7)


# --- NaN handling (SQL NULL via pandas) ------------------------------------

def test_parse_numeric_treats_nan_as_unknown():
    assert parse_numeric(float("nan")) is None


def test_nan_stock_is_not_reported_as_out_of_stock():
    buy = build_buy_info({"price": 1000, "units_available": float("nan")})
    assert buy["units_available"] is None
    assert buy["in_stock"] is None


def test_tool_records_are_json_safe():
    cleaned = _clean_record({"mrp": float("nan"), "price": 10, "created_at": pd.Timestamp("2024-01-01")})
    assert cleaned["mrp"] is None
    assert cleaned["price"] == 10
    assert not any(isinstance(v, float) and math.isnan(v) for v in cleaned.values())


def test_internal_columns_never_become_spec_pills():
    picks = build_top_picks([{
        "name": "X", "brand": "Acme", "price": 10, "ram": "8GB",
        "customer_feedback": "Great!", "ingestion_status": "complete", "_scores": {"overall": 0.9},
    }])
    assert set(picks[0]["specs"]) == {"brand", "ram"}


# --- Orchestrator ----------------------------------------------------------

def test_remove_sentinel_matches_by_value_after_deserialization():
    # A checkpoint round-trip hands back an equal-but-distinct string.
    sentinel_copy = "".join(["__remove", "__"])
    assert sentinel_copy is not ORCHE._REMOVE
    assert ORCHE._merge_dict({"Mobile": {"x": 1}}, {"Mobile": sentinel_copy}) == {}


@pytest.mark.parametrize(
    "offline, city, expected",
    [
        ("Available at Trein T Nagar, Koramangala", "chennai", True),
        ("Available at Trein Koramangala", "bengaluru", True),
        ("Available at Trein Koramangala", "chennai", False),
        # The old word-by-word check matched the lone "t" of "T Nagar"
        # against almost any text.
        ("Available at Croma outlets", "chennai", False),
        ("Stocked in Hyderabad", "hyderabad", True),
    ],
)
def test_available_in_city(offline, city, expected):
    assert ORCHE._available_in_city(offline, city) is expected


# --- Rate limiter ----------------------------------------------------------

def _limited_app(limit):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=limit, window_seconds=60)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


def test_health_endpoint_is_never_rate_limited():
    client = TestClient(_limited_app(1))
    assert all(client.get("/api/health").status_code == 200 for _ in range(5))


def test_prune_drops_clients_whose_window_expired():
    limiter = RateLimitMiddleware(FastAPI(), requests_per_minute=5, window_seconds=60)
    limiter._hits["1.1.1.1"].append(0.0)
    limiter._hits["2.2.2.2"].append(100.0)
    limiter._prune(now=120.0)
    assert list(limiter._hits) == ["2.2.2.2"]
