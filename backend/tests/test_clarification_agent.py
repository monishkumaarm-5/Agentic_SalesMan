"""
Tests for AGENTS/CLARIFICATION_AGENT.py.

assess_sufficiency() and assess_result_quality() are the two halves
WORKFLOW/ORCHE.py's _run_one_category calls around hybrid_search() now
(sufficiency before, so a vague turn never touches the vector DB at all;
result-quality after, for the "zero candidates" case). assess_clarity()
is kept as a backward-compatible wrapper composing both and is tested
separately at the bottom.

The LLM calls are mocked via _call_consultation_llm / _call_sufficiency_llm
-- the module's actual entry points for round-based and post-minimum-
rounds LLM calls (not a single _call_llm, which no longer exists here).
"""
from unittest.mock import patch

from AGENTS.CLARIFICATION_AGENT import (
    ClarityCheck,
    ConsultationQuestion,
    FollowupIntent,
    MIN_CONSULTATION_ROUNDS,
    assess_clarity,
    assess_followup_intent,
    assess_result_quality,
    assess_sufficiency,
)


# ---------- assess_result_quality (post-retrieval, deterministic) ------


def test_zero_candidates_always_needs_clarification():
    result = assess_result_quality([], "phone")
    assert result["needs_clarification"] is True
    assert result["missing"] == ["matching_products"]
    assert "phone" in result["question"]


def test_zero_candidates_question_mentions_the_company_name():
    result = assess_result_quality(None, "refrigerator", company_name="Trein")
    assert "Trein" in result["question"]


def test_nonempty_candidates_need_no_clarification_and_call_no_llm():
    with patch("AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm") as mock_llm:
        result = assess_result_quality([{"name": "iPhone 14"}], "phone")
    mock_llm.assert_not_called()
    assert result == {"needs_clarification": False, "question": None, "missing": []}


# ---------- assess_sufficiency (pre-retrieval) --------------------------


def test_below_min_rounds_always_asks_a_consultation_question_without_the_sufficiency_llm():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_consultation_llm",
        return_value=ConsultationQuestion(clarifying_question="What's your budget?", missing=["budget"]),
    ) as mock_consult, patch("AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm") as mock_sufficiency:
        result = assess_sufficiency("I want a phone", "phone", consultation_rounds=0)

    mock_consult.assert_called_once()
    mock_sufficiency.assert_not_called()
    assert result == {"needs_clarification": True, "question": "What's your budget?", "missing": ["budget"]}


def test_consultation_llm_failure_falls_back_to_a_default_question():
    with patch("AGENTS.CLARIFICATION_AGENT._call_consultation_llm", side_effect=RuntimeError("timeout")):
        result = assess_sufficiency("I want a phone", "phone", consultation_rounds=0)
    assert result["needs_clarification"] is True
    assert "phone" in result["question"]
    assert result["missing"] == ["consultation_llm_error"]


def test_at_min_rounds_uses_the_sufficiency_llm_instead():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm",
        return_value=ClarityCheck(sufficient=True),
    ) as mock_sufficiency, patch("AGENTS.CLARIFICATION_AGENT._call_consultation_llm") as mock_consult:
        result = assess_sufficiency(
            "under 50k, for gaming", "phone", consultation_rounds=MIN_CONSULTATION_ROUNDS
        )

    mock_consult.assert_not_called()
    mock_sufficiency.assert_called_once()
    assert result == {"needs_clarification": False, "question": None, "missing": []}


def test_insufficient_sufficiency_result_returns_its_own_question_and_missing_fields():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm",
        return_value=ClarityCheck(sufficient=False, clarifying_question="Any brand preference?", missing=["brand"]),
    ):
        result = assess_sufficiency("a phone", "phone", consultation_rounds=MIN_CONSULTATION_ROUNDS)
    assert result["needs_clarification"] is True
    assert result["question"] == "Any brand preference?"
    assert result["missing"] == ["brand"]


def test_insufficient_result_falls_back_to_a_default_question_when_none_given():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm",
        return_value=ClarityCheck(sufficient=False, clarifying_question=None, missing=[]),
    ):
        result = assess_sufficiency("a phone", "phone", consultation_rounds=MIN_CONSULTATION_ROUNDS)
    assert result["needs_clarification"] is True
    assert "phone" in result["question"]


def test_sufficiency_llm_failure_fails_open_and_does_not_ask():
    with patch("AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm", side_effect=RuntimeError("timeout")):
        result = assess_sufficiency("a good phone", "phone", consultation_rounds=MIN_CONSULTATION_ROUNDS)
    assert result == {"needs_clarification": False, "question": None, "missing": []}


def test_sufficiency_never_touches_candidates_or_the_vector_db():
    """The whole point of the pre-retrieval split: assess_sufficiency
    takes no `candidates` argument at all -- it can't accidentally depend
    on retrieval results, because ORCHE.py calls it before hybrid_search
    runs."""
    import inspect

    params = inspect.signature(assess_sufficiency).parameters
    assert "candidates" not in params


# ---------- assess_clarity (backward-compatible wrapper) ---------------


def test_assess_clarity_asks_on_zero_candidates_without_calling_sufficiency():
    with patch("AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm") as mock_llm, patch(
        "AGENTS.CLARIFICATION_AGENT._call_consultation_llm"
    ) as mock_consult:
        result = assess_clarity("recommend a phone", "phone", candidates=[])
    mock_llm.assert_not_called()
    mock_consult.assert_not_called()
    assert result["needs_clarification"] is True
    assert result["missing"] == ["matching_products"]


def test_assess_clarity_defers_to_sufficiency_when_candidates_exist():
    candidates = [{"name": "iPhone 14"}]
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_sufficiency_llm",
        return_value=ClarityCheck(sufficient=True),
    ):
        result = assess_clarity(
            "a good phone", "phone", candidates=candidates, consultation_rounds=MIN_CONSULTATION_ROUNDS
        )
    assert result == {"needs_clarification": False, "question": None, "missing": []}


# ---------- assess_followup_intent (doubt/opinion vs fresh request) ----


def test_no_shown_products_is_never_a_followup_and_calls_no_llm():
    """Nothing has been shown yet -- there's nothing to be a follow-up
    about, so this must short-circuit without an LLM call."""
    with patch("AGENTS.CLARIFICATION_AGENT._call_followup_llm") as mock_llm:
        result = assess_followup_intent("what do you think?", product_names=[])
    mock_llm.assert_not_called()
    assert result == {"is_followup": False}


def test_llm_says_followup_is_passed_through():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_followup_llm",
        return_value=FollowupIntent(is_followup=True),
    ):
        result = assess_followup_intent(
            "what do you think about the Noise Buds?",
            product_names=["Noise Buds Aero"],
        )
    assert result == {"is_followup": True}


def test_llm_says_fresh_request_is_passed_through():
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_followup_llm",
        return_value=FollowupIntent(is_followup=False),
    ):
        result = assess_followup_intent(
            "actually show me something under 500 instead",
            product_names=["Noise Buds Aero"],
        )
    assert result == {"is_followup": False}


def test_followup_llm_failure_fails_open_to_fresh_request():
    """Failing open here means "search again", not "answer from stale
    data" -- the safer of the two outcomes when the LLM call itself
    breaks."""
    with patch(
        "AGENTS.CLARIFICATION_AGENT._call_followup_llm",
        side_effect=RuntimeError("timeout"),
    ):
        result = assess_followup_intent(
            "what do you think?", product_names=["Noise Buds Aero"],
        )
    assert result == {"is_followup": False}
