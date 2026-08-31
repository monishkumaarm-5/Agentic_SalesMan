"""
Tests for AGENTS/EXIT_SAFE_GAURD_AGENT.py's scored evaluator. The LLM call
itself is mocked via `_call_llm` (see that module) -- these tests are about
the scoring/threshold/fail-open logic, not model quality.
"""
from unittest.mock import patch

from AGENTS.EXIT_SAFE_GAURD_AGENT import Evaluation, evaluate_response


def _eval(**overrides):
    base = dict(
        groundedness=0.9,
        relevance=0.9,
        product_accuracy=0.9,
        constraint_satisfaction=0.9,
        sales_quality=0.9,
        reasons=[],
    )
    base.update(overrides)
    return Evaluation(**base)


def test_high_scores_pass():
    with patch("AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm", return_value=_eval()):
        result = evaluate_response("q", "a", [], {})
    assert result["passed"] is True
    assert result["overall"] == 0.9


def test_low_average_fails():
    with patch("AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm", return_value=_eval(
        groundedness=0.5, relevance=0.5, product_accuracy=0.5, constraint_satisfaction=0.5, sales_quality=0.5
    )):
        result = evaluate_response("q", "a", [], {}, min_score=0.6)
    assert result["passed"] is False
    assert result["overall"] == 0.5


def test_hallucination_hard_fails_even_with_a_good_average():
    """A high average with a hallucinated product/spec should still fail --
    groundedness and product_accuracy are a hard gate, not just inputs to
    the average."""
    with patch("AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm", return_value=_eval(
        groundedness=0.1, product_accuracy=0.1, relevance=1.0, constraint_satisfaction=1.0, sales_quality=1.0
    )):
        result = evaluate_response("q", "a", [], {}, min_score=0.5)
    assert result["passed"] is False


def test_reasons_are_surfaced_for_retry_feedback():
    with patch(
        "AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm",
        return_value=_eval(groundedness=0.1, product_accuracy=0.1, reasons=["invented a 'Pro Max' variant"]),
    ):
        result = evaluate_response("q", "a", [], {})
    assert "invented a 'Pro Max' variant" in result["reasons"]


def test_evaluator_fails_open_when_the_llm_call_errors():
    with patch("AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm", side_effect=RuntimeError("rate limited")):
        result = evaluate_response("q", "a", [], {})
    assert result["passed"] is True
    assert result["overall"] is None


def test_scores_are_clamped_to_zero_one_even_if_the_llm_misbehaves():
    with patch("AGENTS.EXIT_SAFE_GAURD_AGENT._call_llm", return_value=_eval(
        groundedness=5.0, relevance=-2.0
    )):
        result = evaluate_response("q", "a", [], {}, min_score=0.0)
    assert result["scores"]["groundedness"] == 1.0
    assert result["scores"]["relevance"] == 0.0
