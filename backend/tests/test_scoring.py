"""Tests for WORKFLOW/scoring.py's recommendation scoring engine."""
from WORKFLOW.scoring import (
    brand_fit_score,
    budget_fit_score,
    rating_score,
    score_candidate,
    spec_match_score,
)


def test_budget_fit_is_perfect_within_budget():
    assert budget_fit_score(50000, 80000) == 1.0


def test_budget_fit_decays_over_budget():
    score = budget_fit_score(100000, 80000)  # 25% over
    assert 0.0 < score < 1.0


def test_budget_fit_clamps_at_zero_for_wildly_over_budget():
    assert budget_fit_score(1_000_000, 10_000) == 0.0


def test_budget_fit_is_neutral_when_unknown():
    assert budget_fit_score(None, 80000) == 0.7
    assert budget_fit_score(50000, None) == 0.7


def test_spec_match_rewards_ram_for_ml_use_case():
    high_ram = {"ram": "32GB", "processor": "i7 RTX 4060"}
    low_ram = {"ram": "8GB", "processor": "i3"}
    high_score = spec_match_score(high_ram, ["machine learning"])
    low_score = spec_match_score(low_ram, ["machine learning"])
    assert high_score > low_score


def test_spec_match_is_neutral_with_no_use_cases():
    assert spec_match_score({"ram": "8GB"}, []) == 0.7


def test_spec_match_is_neutral_for_unrecognized_use_cases():
    assert spec_match_score({"ram": "8GB"}, ["underwater basket weaving"]) == 0.7


def test_rating_score_unavailable_when_no_rating_column():
    score, available = rating_score({"name": "X", "price": 100})
    assert available is False
    assert score == 0.0


def test_rating_score_normalizes_five_point_scale():
    score, available = rating_score({"rating": 4.5})
    assert available is True
    assert score == 0.9


def test_rating_score_normalizes_ten_point_scale():
    score, available = rating_score({"review_score": 9})
    assert available is True
    assert score == 0.9


def test_brand_fit_matches_case_insensitively():
    assert brand_fit_score("Lenovo", "lenovo") == 1.0


def test_brand_fit_penalizes_mismatch():
    assert brand_fit_score("HP", "Lenovo") == 0.3


def test_brand_fit_is_neutral_when_no_preference():
    assert brand_fit_score("HP", None) == 0.7


def test_score_candidate_redistributes_rating_weight_when_absent():
    row = {"name": "X", "brand": "Lenovo", "ram": "16GB", "price": 70000}
    result = score_candidate(row, {}, semantic_score=0.8)
    assert "rating" not in result["components"]
    assert result["rating_available"] is False
    assert abs(sum(result["weights"].values()) - 1.0) < 1e-3


def test_score_candidate_keeps_rating_weight_when_present():
    row = {"name": "X", "brand": "Lenovo", "ram": "16GB", "price": 70000, "rating": 4.8}
    result = score_candidate(row, {}, semantic_score=0.8)
    assert "rating" in result["components"]
    assert abs(sum(result["weights"].values()) - 1.0) < 1e-3


def test_score_candidate_overall_is_bounded():
    row = {"name": "X", "brand": "Lenovo", "ram": "64GB", "price": 1}
    result = score_candidate(row, {"budget_max": 1000000, "brand": "Lenovo"}, semantic_score=1.0)
    assert 0.0 <= result["overall"] <= 1.0


def test_score_candidate_ranks_better_fit_higher():
    good_fit = {"name": "Good", "brand": "Lenovo", "ram": "16GB", "price": 70000}
    bad_fit = {"name": "Bad", "brand": "HP", "ram": "4GB", "price": 200000}
    requirements = {"budget_max": 80000, "use_cases": ["programming"], "brand": "Lenovo"}
    good_score = score_candidate(good_fit, requirements, semantic_score=0.7)["overall"]
    bad_score = score_candidate(bad_fit, requirements, semantic_score=0.7)["overall"]
    assert good_score > bad_score
