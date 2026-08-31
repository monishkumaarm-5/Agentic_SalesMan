"""
Exit evaluator: the quality gate every sales-agent answer passes through
before it reaches the customer.

This used to be a single True/False safety check (a stub before this
project's first pass, then a plain boolean LLM call). It's now a scored,
5-dimension evaluation -- groundedness, relevance, product accuracy,
constraint satisfaction and sales quality -- because a boolean can't tell
WORKFLOW/ORCHE.py's retry logic *why* an answer was rejected, and can't
distinguish "slightly off-topic" from "confidently hallucinated a product
that doesn't exist" (the latter is treated as a hard failure regardless of
the other four scores -- see the groundedness/product_accuracy gate below).

Like the entry guard, this fails open: if the evaluator LLM call itself
errors, the answer is passed through rather than blocked, with a warning
logged. An evaluator that can take the whole chat down whenever Gemini has a
bad moment would be worse than no evaluator.
"""
import logging
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from WORKFLOW.retrieval import format_candidates_for_prompt

logger = logging.getLogger("agentic_salesman.evaluator")

# Below this, an answer is rejected outright no matter how the other four
# dimensions score -- a well-written, on-topic, hallucinated recommendation
# is a worse outcome than a mediocre but honest one.
HARD_FAIL_THRESHOLD = 0.4

prompt_template = PromptTemplate.from_template(
    """
    Role: Quality evaluator for an e-commerce sales agent's response.
    Task: Score the assistant's answer against the customer's question and
    the product data it was allowed to use. Be strict about grounding --
    any price, spec or product name not present in the product data below
    should lower groundedness and product_accuracy sharply.

    Score each dimension from 0.0 (fails completely) to 1.0 (excellent):
    - groundedness: every factual claim (price, specs, availability) traces
      back to the product data below. Nothing invented.
    - relevance: the answer actually addresses the customer's question.
    - product_accuracy: prices/specs mentioned match the product data
      exactly.
    - constraint_satisfaction: the recommendation respects any stated
      constraints (budget, brand, use case) reflected in the requirements
      below.
    - sales_quality: helpful, honest, well-organized, not manipulative or
      falsely urgent.

    Also give a short list of `reasons` (1-4 short strings) explaining the
    scores, especially anything that failed -- these are shown to a retry
    step, so be specific enough that a rewrite could act on them (e.g.
    "mentioned a 'Pro Max' variant not present in product data").

    Output ONLY JSON matching the schema below.

    Customer's question:
    {question}

    Extracted requirements:
    {requirements}

    Product data the answer was allowed to use:
    {product_data}

    Assistant's answer:
    {answer}
    """
)


class Evaluation(BaseModel):
    groundedness: float
    relevance: float
    product_accuracy: float
    constraint_satisfaction: float
    sales_quality: float
    reasons: List[str] = Field(default_factory=list)


llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
structured_llm = llm.with_structured_output(Evaluation)

DIMENSIONS = (
    "groundedness",
    "relevance",
    "product_accuracy",
    "constraint_satisfaction",
    "sales_quality",
)


def _clamp(value: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _call_llm(question: str, answer: str, product_data: str, requirements_text: str) -> Evaluation:
    """Isolated so tests can monkeypatch just the LLM call (see
    tests/test_evaluator.py) without needing a real LangChain Runnable
    chain in place of the LLM."""
    chain = prompt_template | structured_llm
    return chain.invoke(
        {
            "question": question,
            "answer": answer,
            "product_data": product_data,
            "requirements": requirements_text,
        }
    )


def evaluate_response(
    question: str,
    answer: str,
    candidates: Optional[list] = None,
    requirements: Optional[dict] = None,
    min_score: float = 0.6,
) -> dict:
    """Returns {"scores": {...5 dims...}, "overall": float, "passed": bool,
    "reasons": [...]}. `overall` is the plain average of the 5 dimensions;
    `passed` additionally requires groundedness and product_accuracy to
    both clear HARD_FAIL_THRESHOLD, since those two catch hallucination
    specifically."""
    product_data = format_candidates_for_prompt(candidates or [])
    requirements_text = str(requirements or {})

    try:
        result = _call_llm(question, answer, product_data, requirements_text)
        scores = {dim: _clamp(getattr(result, dim)) for dim in DIMENSIONS}
        overall = sum(scores.values()) / len(scores)
        hard_fail = (
            scores["groundedness"] < HARD_FAIL_THRESHOLD
            or scores["product_accuracy"] < HARD_FAIL_THRESHOLD
        )
        passed = overall >= min_score and not hard_fail
        return {
            "scores": scores,
            "overall": round(overall, 4),
            "passed": passed,
            "reasons": list(result.reasons or []),
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Evaluator call failed (%s); passing answer through", exc)
        return {
            "scores": None,
            "overall": None,
            "passed": True,
            "reasons": [f"evaluator unavailable: {exc}"],
        }
