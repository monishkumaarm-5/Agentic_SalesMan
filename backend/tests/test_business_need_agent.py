"""
Tests for AGENTS/BUSINESS_NEED_AGENT.py.

Two behaviours added after a real bug report: several rounds into an
iPhone/Mobile consultation, the LLM started asking about "laptop" instead
-- traced to (a) `assess()` re-inferring `categories` from scratch every
round with nothing telling it what category was already established
(fixed by threading `current_categories` into the prompt as an anchor),
and (b) the consultation never converging because `satisfied` was purely
an LLM judgment call with no code-enforced ceiling (fixed by
MAX_CONSULTATION_ROUNDS). ORCHE.py's own corroboration guard against an
uncorroborated category switch is covered in tests/test_orche.py; this
file covers `assess()`'s own contract in isolation, same pattern as
tests/test_clarification_agent.py.

The LLM call is mocked via `_call_llm`.
"""
from unittest.mock import patch

from AGENTS.BUSINESS_NEED_AGENT import (
    BusinessNeedAssessment,
    MAX_CONSULTATION_ROUNDS,
    MIN_CONSULTATION_ROUNDS,
    assess,
)


def _assessment(**overrides):
    defaults = dict(
        is_shopping_request=True,
        categories=["Mobile"],
        budget_max=80000,
        use_cases=["gaming"],
        brand=None,
        motivation=None,
        pain_points=[],
        urgency_level="Medium",
        satisfied=False,
        reply="What size display do you want?",
    )
    defaults.update(overrides)
    return BusinessNeedAssessment(**defaults)


def test_current_categories_is_forwarded_to_the_llm_call_as_an_anchor():
    with patch(
        "AGENTS.BUSINESS_NEED_AGENT._call_llm", return_value=_assessment()
    ) as mock_llm:
        assess(
            "brand new model", ["Mobile", "Laptop"],
            history="...", consultation_rounds=3, current_categories=["Mobile"],
        )
    args, kwargs = mock_llm.call_args
    # _call_llm(question, history, category_list, company_name, round_number, current_categories)
    assert args[-1] == "Mobile"


def test_no_current_categories_forwards_empty_string_not_none():
    with patch(
        "AGENTS.BUSINESS_NEED_AGENT._call_llm", return_value=_assessment()
    ) as mock_llm:
        assess("I need a phone", ["Mobile", "Laptop"])
    args, kwargs = mock_llm.call_args
    assert args[-1] == ""


def test_below_max_rounds_a_dissatisfied_llm_response_stays_unsatisfied():
    # round_number = consultation_rounds + 1 = 2, MAX is 4 -- nowhere near
    # the ceiling, so the LLM's own `satisfied=False` should be respected.
    with patch(
        "AGENTS.BUSINESS_NEED_AGENT._call_llm",
        return_value=_assessment(satisfied=False),
    ):
        result = assess(
            "80k budget", ["Mobile"],
            consultation_rounds=1, current_categories=["Mobile"],
        )
    assert result["satisfied"] is False


def test_hitting_max_rounds_forces_satisfied_even_if_the_llm_kept_asking():
    # consultation_rounds + 1 == MAX_CONSULTATION_ROUNDS -- the ceiling
    # forces convergence in code even though the (mocked) LLM is still
    # returning satisfied=False, guarding against a real model that keeps
    # finding "just one more" optional detail to ask about.
    with patch(
        "AGENTS.BUSINESS_NEED_AGENT._call_llm",
        return_value=_assessment(satisfied=False, reply="What color do you prefer?"),
    ):
        result = assess(
            "any color is fine", ["Mobile"],
            consultation_rounds=MAX_CONSULTATION_ROUNDS - 1,
            current_categories=["Mobile"],
        )
    assert result["satisfied"] is True


def test_max_rounds_ceiling_never_forces_satisfaction_with_no_category():
    # The ceiling only forces convergence once a category is actually
    # known -- it must never wave through a search with no category at
    # all just because the round count is high.
    with patch(
        "AGENTS.BUSINESS_NEED_AGENT._call_llm",
        return_value=_assessment(satisfied=False, categories=[]),
    ):
        result = assess(
            "still not sure what I want", [],
            consultation_rounds=MAX_CONSULTATION_ROUNDS - 1,
        )
    assert result["satisfied"] is False


def test_max_rounds_ceiling_respects_the_min_rounds_floor():
    # MAX_CONSULTATION_ROUNDS is defined to sit at or above
    # MIN_CONSULTATION_ROUNDS -- a config error here would let the
    # ceiling force `satisfied=True` before the minimum-rounds floor
    # is met, defeating the floor entirely.
    assert MAX_CONSULTATION_ROUNDS >= MIN_CONSULTATION_ROUNDS
