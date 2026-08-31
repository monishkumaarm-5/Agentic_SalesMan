"""
Structured requirement extraction: turns free-form conversation into the
{budget_max, use_cases, brand} dict that WORKFLOW/retrieval.py and
WORKFLOW/scoring.py use for hybrid SQL+vector search and recommendation
scoring.

This is what lets a follow-up like "under $1000" or "I prefer Lenovo" -- said
after "recommend a laptop for coding" -- actually change which products get
surfaced, not just the sales agent's prose. It's a small, single-purpose LLM
call (same pattern as the entry guard), kept separate from the entry guard
itself so a change to one prompt can't silently break the other's output
schema.
"""
import logging
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

logger = logging.getLogger("agentic_salesman.requirements")

prompt_template = PromptTemplate.from_template(
    """
    Role: Requirement Extraction Assistant supporting an e-commerce sales
    agent for phones, laptops and headphones.
    Task: Read the conversation and extract structured shopping
    requirements. Do not answer the customer -- only extract requirements.

    Extract:
    - budget_max: the maximum price the customer mentioned, as a plain
      number with no currency symbol or commas (e.g. 80000, not "₹80,000").
      null if no budget was mentioned.
    - use_cases: a short list of concise, lowercase use-case phrases implied
      by the request (e.g. "machine learning", "gaming", "programming",
      "student", "battery life", "camera", "noise cancelling"). Empty list
      if nothing specific was implied.
    - brand: a specific brand the customer asked for (e.g. "Lenovo",
      "Apple"). null if none was mentioned.

    Output ONLY JSON matching the schema below -- no explanation.
    {{
        "budget_max": null,
        "use_cases": [],
        "brand": null
    }}
    -------------------------------------------------------------------------
    Conversation so far (most recent last):
    {context}

    Customer's current message:
    {question}
    """
)


class Requirements(BaseModel):
    budget_max: Optional[float] = None
    use_cases: List[str] = Field(default_factory=list)
    brand: Optional[str] = None


llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_llm = llm.with_structured_output(Requirements)

EMPTY_REQUIREMENTS = {"budget_max": None, "use_cases": [], "brand": None}


def _call_llm(question: str, context: str) -> Requirements:
    """Isolated so tests can monkeypatch just the LLM call (see
    tests/test_requirement_extractor.py) without needing a real LangChain
    Runnable chain in place of the LLM."""
    chain = prompt_template | structured_llm
    return chain.invoke({"question": question, "context": context})


def extract_requirements(question: str, context: str = "") -> dict:
    """Never raises -- a failed/malformed extraction just means every
    scoring component that depends on it (budget fit, spec match, brand
    fit) falls back to its own neutral score (see WORKFLOW/scoring.py)
    rather than blocking the chat turn."""
    try:
        result = _call_llm(question, context or "(no prior conversation)")
        return {
            "budget_max": result.budget_max,
            "use_cases": [uc for uc in (result.use_cases or []) if uc],
            "brand": result.brand or None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Requirement extraction failed (%s); using empty requirements", exc)
        return dict(EMPTY_REQUIREMENTS)
