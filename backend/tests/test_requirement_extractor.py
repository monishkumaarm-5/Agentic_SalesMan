"""
Tests for AGENTS/REQUIREMENT_EXTRACTOR_AGENT.py. The LLM call is mocked via
`_call_llm` -- these tests are about the fail-open/normalization behaviour,
not model quality.
"""
from unittest.mock import patch

from AGENTS.REQUIREMENT_EXTRACTOR_AGENT import Requirements, extract_requirements


def test_extracts_budget_use_cases_and_brand():
    fake_result = Requirements(budget_max=80000, use_cases=["gaming", "programming"], brand="Lenovo")
    with patch("AGENTS.REQUIREMENT_EXTRACTOR_AGENT._call_llm", return_value=fake_result):
        result = extract_requirements("laptop under 80k for gaming and coding, Lenovo preferred")
    assert result == {"budget_max": 80000, "use_cases": ["gaming", "programming"], "brand": "Lenovo"}


def test_defaults_to_empty_requirements_when_nothing_extracted():
    fake_result = Requirements()
    with patch("AGENTS.REQUIREMENT_EXTRACTOR_AGENT._call_llm", return_value=fake_result):
        result = extract_requirements("recommend a laptop")
    assert result == {"budget_max": None, "use_cases": [], "brand": None}


def test_filters_out_falsy_use_cases():
    fake_result = Requirements(use_cases=["gaming", ""])
    with patch("AGENTS.REQUIREMENT_EXTRACTOR_AGENT._call_llm", return_value=fake_result):
        result = extract_requirements("a gaming laptop")
    assert result["use_cases"] == ["gaming"]


def test_fails_open_to_empty_requirements_on_llm_error():
    with patch("AGENTS.REQUIREMENT_EXTRACTOR_AGENT._call_llm", side_effect=RuntimeError("boom")):
        result = extract_requirements("anything")
    assert result == {"budget_max": None, "use_cases": [], "brand": None}
