import pytest

from app.catalog.utils import format_price, humanize, json_safe, parse_numeric
from app.models import ShoppingProfile
from app.retrieval import scoring
from app.retrieval.cards import build_card, match_name
from app.retrieval.search import budget_note, hybrid_search
from tests.conftest import PRODUCTS, semantic_search

M35, REDMI, IPHONE = PRODUCTS[0], PRODUCTS[1], PRODUCTS[2]


@pytest.mark.parametrize("value, expected", [
    (16, 16.0), ("16GB", 16.0), ("1TB", 1000.0), ("₹45,999", 45999.0), ("n/a", None),
    (float("nan"), None), (None, None), (True, None),
])
def test_parse_numeric(value, expected):
    assert parse_numeric(value) == expected


def test_formatting_helpers():
    assert format_price(1234567) == "₹12,34,567"
    assert humanize("battery_life") == "Battery life" and humanize("ram") == "RAM"
    assert json_safe({"a": float("nan"), "b": [1, float("nan")]}) == {"a": None, "b": [1, None]}


def test_profile_cleans_input():
    p = ShoppingProfile(categories=["Mobile", "mobile", " "], budget_max="0", must_haves="5G")
    assert p.categories == ["Mobile"] and p.budget_max is None and p.must_haves == ["5G"]


def test_budget_score():
    p = ShoppingProfile(budget_max=20000)
    assert scoring.budget_score(18999, p) == 1.0
    assert scoring.budget_score(21999, p) < 1.0
    assert scoring.budget_score(69999, p) == 0.0
    assert scoring.budget_score(18999, ShoppingProfile()) is None


def test_feature_matching_is_driven_by_what_the_customer_asked():
    p = ShoppingProfile(must_haves=["AMOLED", "6000mAh battery", "wireless charging"])
    matched, unmatched = scoring.feature_matches(M35, p)
    assert matched == ["AMOLED", "6000mAh battery"] and unmatched == ["wireless charging"]
    assert scoring.feature_matches(M35, ShoppingProfile(must_haves=["8 GB RAM"]))[0] == ["8 GB RAM"]


def test_missing_signals_do_not_penalise():
    bare = {"name": "X", "price": 100}
    s = scoring.score_product(bare, ShoppingProfile(), relevance=0.8)
    assert s["overall"] == pytest.approx(0.8)
    assert set(s["components"]) == {"relevance"}


def test_brand_and_availability():
    assert scoring.brand_score(IPHONE, ShoppingProfile(avoid_brands=["apple"])) == 0.0
    assert scoring.brand_score(IPHONE, ShoppingProfile(preferred_brands=["Apple"])) == 1.0
    assert scoring.availability_score(IPHONE, ShoppingProfile()) == 0.2  # out of stock
    near = scoring.availability_score(REDMI, ShoppingProfile(city="Chennai"))
    far = scoring.availability_score(M35, ShoppingProfile(city="Chennai"))
    assert near > far


def test_hybrid_search_ranks_by_fit_not_just_similarity():
    p = ShoppingProfile(categories=["Mobile"], budget_max=20000)
    results = hybrid_search(semantic_search, "phone", p, "Mobile", top_k=3)
    assert results[0]["name"] == "Redmi Note 14"  # 2nd by similarity, 1st by fit
    assert results[-1]["name"] == "iPhone 15"


def test_hybrid_search_excludes_and_avoids():
    p = ShoppingProfile(avoid_brands=["Samsung"])
    names = [r["name"] for r in hybrid_search(semantic_search, "phone", p, "Mobile", exclude_names=["iPhone 15"])]
    assert names == ["Redmi Note 14"]


def test_hybrid_search_falls_back_to_catalog_rows():
    def broken(*_):
        raise RuntimeError("index down")
    rows = hybrid_search(broken, "phone", ShoppingProfile(), "Mobile", fallback=lambda c: [dict(p) for p in PRODUCTS[:2]])
    assert len(rows) == 2


def test_budget_note_only_when_nothing_fits():
    assert budget_note([IPHONE], ShoppingProfile(budget_max=20000))
    assert budget_note([REDMI, IPHONE], ShoppingProfile(budget_max=20000)) is None


def test_card_contains_only_catalog_facts():
    row = {**M35, "_scores": scoring.score_product(M35, ShoppingProfile(city="Bengaluru"), 0.9)}
    card = build_card(row, {"headline": "Big battery", "why": "Lasts two days"}, rank=1, city="Bengaluru")
    assert card["discount_percent"] == 12 and card["in_stock"] is True
    assert [s["label"] for s in card["specs"]] == ["RAM", "Storage", "Battery"]
    assert card["stores"][0]["name"] == "Trein Koramangala" and card["stores"][0]["nearby"]
    assert card["headline"] == "Big battery"


def test_match_name():
    assert match_name("redmi note 14", PRODUCTS)["id"] == 2
    assert match_name("The Galaxy M35 5G phone", PRODUCTS)["id"] == 1
    assert match_name("Pixel 9", PRODUCTS) is None
