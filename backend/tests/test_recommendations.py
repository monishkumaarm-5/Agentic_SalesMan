"""
Tests for WORKFLOW/recommendations.py -- the deterministic merge of scored
retrieval candidates (see WORKFLOW/retrieval.py) with the sales agent's own
per-product narrative into the "top pick" cards the API returns under
ChatResponse.product.
"""
from WORKFLOW.recommendations import build_buy_info, build_top_picks


def _candidate(**overrides):
    base = {
        "name": "HP Pavilion 15",
        "brand": "HP",
        "price": 69990,
        "ram": "16GB",
        "storage": "512GB",
        "_scores": {"overall": 0.91},
    }
    base.update(overrides)
    return base


def test_build_buy_info_computes_discount_when_mrp_present():
    info = build_buy_info(_candidate(mrp=99990))
    assert info["price"] == 69990
    assert info["mrp"] == 99990
    assert info["discount_percentage"] == 30.0


def test_build_buy_info_never_invents_fields_the_catalog_does_not_track():
    info = build_buy_info(_candidate())
    assert info["discount_percentage"] is None
    assert info["units_available"] is None
    assert info["online_link"] is None
    assert info["offline_availability"] is None
    assert info["in_stock"] is None


def test_build_buy_info_reads_units_and_derives_in_stock():
    in_stock_info = build_buy_info(_candidate(stock=5))
    assert in_stock_info["units_available"] == 5
    assert in_stock_info["in_stock"] is True

    out_of_stock_info = build_buy_info(_candidate(stock=0))
    assert out_of_stock_info["units_available"] == 0
    assert out_of_stock_info["in_stock"] is False


def test_build_buy_info_reads_link_and_offline_columns_case_insensitively():
    info = build_buy_info(
        _candidate(
            **{
                "Online_Link": "https://example.com/x",
                "Offline_Stores": "Croma, Reliance Digital",
            }
        )
    )
    assert info["online_link"] == "https://example.com/x"
    assert info["offline_availability"] == "Croma, Reliance Digital"


def test_build_buy_info_no_discount_when_price_meets_or_exceeds_mrp():
    info = build_buy_info(_candidate(mrp=50000))  # price (69990) > mrp
    assert info["discount_percentage"] is None


def test_build_top_picks_ranks_by_score_not_narrative_order():
    candidates = [
        _candidate(name="A", price=1000, _scores={"overall": 0.9}),
        _candidate(name="B", price=2000, _scores={"overall": 0.5}),
    ]
    narratives = [
        {"name": "B", "why_this": "B reason"},
        {"name": "A", "why_this": "A reason"},
    ]
    picks = build_top_picks(candidates, narratives)
    assert [p["name"] for p in picks] == ["A", "B"]
    assert [p["rank"] for p in picks] == [1, 2]
    assert picks[0]["why_this"] == "A reason"
    assert picks[1]["why_this"] == "B reason"


def test_build_top_picks_tolerates_a_fuzzy_name_match():
    candidates = [_candidate(name="HP Pavilion 15")]
    narratives = [{"name": "HP Pavillion 15", "why_this": "close enough"}]
    picks = build_top_picks(candidates, narratives)
    assert picks[0]["why_this"] == "close enough"


def test_build_top_picks_without_narrative_still_returns_deterministic_data():
    candidates = [_candidate()]
    picks = build_top_picks(candidates, narratives=None)
    assert picks[0]["name"] == "HP Pavilion 15"
    assert picks[0]["buy"]["price"] == 69990
    assert picks[0]["specs"]["ram"] == "16GB"
    assert picks[0]["why_this"] is None
    assert picks[0]["key_features"] == []
    assert picks[0]["why_suits_you"] is None


def test_build_top_picks_caps_at_three():
    candidates = [_candidate(name=str(i), price=i, _scores={"overall": 1 - i / 10}) for i in range(5)]
    picks = build_top_picks(candidates)
    assert len(picks) == 3
    assert [p["rank"] for p in picks] == [1, 2, 3]


def test_build_top_picks_returns_empty_list_for_no_candidates():
    assert build_top_picks([]) == []


def test_build_buy_info_matches_known_store_and_returns_maps_link():
    info = build_buy_info(_candidate(offline_availability="Available at Trein T Nagar"))
    assert info["offline_availability"] == "Available at Trein T Nagar"
    assert len(info["offline_stores"]) == 1
    store = info["offline_stores"][0]
    assert store["name"] == "Trein T Nagar"
    assert store["city"] == "Chennai"
    assert store["maps_url"].startswith("https://www.google.com/maps/search/")
    assert "Usman+Road" in store["maps_url"] or "Usman%20Road" in store["maps_url"]


def test_build_buy_info_matches_multiple_stores_from_comma_list():
    info = build_buy_info(
        _candidate(offline_availability="Trein T Nagar, Trein Koramangala")
    )
    names = {store["name"] for store in info["offline_stores"]}
    assert names == {"Trein T Nagar", "Trein Koramangala"}


def test_build_buy_info_third_party_retailers_yield_no_store_links():
    # "Croma, Reliance Digital" isn't in config.STORE_LOCATIONS -- the raw
    # text still shows, but there's nothing to build a Maps link for.
    info = build_buy_info(_candidate(offline_availability="Croma, Reliance Digital"))
    assert info["offline_availability"] == "Croma, Reliance Digital"
    assert info["offline_stores"] == []


def test_build_buy_info_online_only_phrase_yields_no_store_links():
    info = build_buy_info(_candidate(offline_availability="Online only"))
    assert info["offline_stores"] == []


def test_build_buy_info_no_offline_column_yields_empty_store_list():
    info = build_buy_info(_candidate())
    assert info["offline_stores"] == []
