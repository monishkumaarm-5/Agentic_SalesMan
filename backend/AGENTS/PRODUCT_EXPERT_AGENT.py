"""
Product Expert Agent -- one structured LLM call replacing the old CrewAI
crew's Product Expert + Consumer Psychologist tasks (the "what emotional
angle does this pick need" half of the Psychologist; the intake half of
its job now lives in AGENTS/BUSINESS_NEED_AGENT.py, captured once instead
of re-derived on every recommendation).

Grounded exactly the same way the old crew's product agent was: only
allowed to pick from -- and only allowed to describe features of --
products present in `rag_data` (the already-scored candidates from
WORKFLOW/retrieval.hybrid_search). No live tool-calling loop here (the
old crew's search/compare/inventory/price tools are still available to
MCP clients via TOOLS/product_tools.py, just not wired into this agent's
own reasoning loop) -- deliberately kept simple: retrieval already ran
before this is called, so there's nothing this call needs to go fetch.

Decides, in the same call:
  - which of the retrieved candidates to feature and why (top_picks,
    matched onto the deterministic scored candidates by
    WORKFLOW.recommendations.build_top_picks, same as before),
  - whether that's actually satisfying (`satisfied`) or the customer's
    message means "still consulting" (more detail, a comparison request)
    vs. "show me a genuinely different search" (`wants_new_search`).
"""
import logging
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from AGENTS.llm import build_llm
from pydantic import BaseModel, Field

logger = logging.getLogger("agentic_salesman.product_expert")

prompt_template = PromptTemplate.from_template(
    """
    Role: Senior {category} Product Expert at {company_name}.

    Goal: From the RAG data below (already ranked best-to-worst by our
    scoring engine), pick the {product} (s) that best fit this customer --
    grounded ONLY in what's actually in the RAG data, never invented.

    What we already know about this customer:
    Business need: {business_need}
    Psychology (why they want this, how to frame it): {customer_psychology}

    Conversation so far:
    {history}

    Customer's current message:
    {question}

    RAG data (ranked best-to-worst -- keep this order, don't re-rank):
    {rag_data}

    STRICT GROUNDING RULE: You may ONLY mention features, specs,
    capabilities, and use cases that are EXPLICITLY written in the RAG
    data below. If a capability is not literally stated (e.g. "4K
    recording", "water resistance", "AI features"), do NOT claim or
    imply the product has it. Do NOT infer capabilities from other
    specs (e.g. "108MP camera" does NOT mean "4K video" unless "4K" is
    explicitly written). When a customer asks about a feature not in
    the data, say "that isn't listed in our catalog info" rather than
    guessing.

    Decide:
    - top_picks: up to 3 entries, in the RAG data's own order, using ONLY
      product names that appear verbatim in the RAG data. Each entry:
      name, why_this (2-3 sentences grounded ONLY in stated specs),
      key_features (list ONLY features explicitly in the RAG data),
      why_suits_you (ties it to the business need + psychology
      above, 1-2 sentences -- only reference specs actually present).
    - satisfied: true if these picks are ready to hand to the sales
      consultant for the final pitch. false if you need the customer to
      say more before recommending responsibly (e.g. the RAG data is thin
      or ambiguous for what they described).
    - still_consulting: true if the customer's current message reads as a
      follow-up ABOUT products you already discussed in this category this
      turn (a spec question, "compare these two", "which is lighter") --
      answer it in `reply` rather than re-searching. false otherwise.
    - wants_new_search: true if the customer's message reads as rejecting
      the current direction entirely (a different budget range, brand, or
      use case that the RAG data above doesn't cover) -- send them back
      for a fresh business-need conversation rather than picking from data
      that no longer fits. false otherwise. (satisfied, still_consulting
      and wants_new_search are mutually exclusive -- exactly one path
      applies.)
    - reply: only used when satisfied is false -- a short, natural message:
      the answer to their follow-up (still_consulting case), or a brief
      acknowledgement that you'll look for something else
      (wants_new_search case).

    Output ONLY JSON matching the schema below -- no prose outside it.
    EVERY feature and spec you mention MUST appear verbatim in the RAG
    data above. If you cannot find a feature in the RAG data, do NOT
    include it:
    {{
        "top_picks": [
            {{"name": "", "why_this": "", "key_features": [], "why_suits_you": ""}}
        ],
        "satisfied": true,
        "still_consulting": false,
        "wants_new_search": false,
        "reply": ""
    }}
    """
)


class TopPickNarrative(BaseModel):
    name: str
    why_this: str = ""
    key_features: List[str] = Field(default_factory=list)
    why_suits_you: str = ""


class ProductAssessment(BaseModel):
    top_picks: List[TopPickNarrative] = Field(default_factory=list)
    satisfied: bool = False
    still_consulting: bool = False
    wants_new_search: bool = False
    reply: str = ""


llm = build_llm()
structured_llm = llm.with_structured_output(ProductAssessment)


def _call_llm(
    question: str,
    category: str,
    product_noun: str,
    business_need: dict,
    customer_psychology: dict,
    history: str,
    rag_data: str,
    company_name: str,
) -> ProductAssessment:
    """Isolated so tests can monkeypatch just the LLM call."""
    chain = prompt_template | structured_llm
    return chain.invoke(
        {
            "question": question,
            "category": category,
            "product": product_noun,
            "business_need": business_need or {},
            "customer_psychology": customer_psychology or {},
            "history": history or "(no prior conversation)",
            "rag_data": rag_data,
            "company_name": company_name,
        }
    )


def recommend(
    question: str,
    category: str,
    product_noun: str,
    business_need: Optional[dict] = None,
    customer_psychology: Optional[dict] = None,
    history: str = "",
    rag_data: str = "",
    company_name: str = "Trein",
) -> dict:
    """Returns a plain dict (never raises):
      narratives (list of {name, why_this, key_features, why_suits_you},
      for WORKFLOW.recommendations.build_top_picks to match onto the
      scored candidates), satisfied, still_consulting, wants_new_search,
      reply.
    Fails open to `satisfied=False, still_consulting=True` with a plain
    apology reply -- never lets an LLM hiccup silently show the customer
    an empty recommendation.
    """
    try:
        result = _call_llm(
            question, category, product_noun, business_need or {},
            customer_psychology or {}, history, rag_data, company_name,
        )
    except Exception as exc:
        logger.warning("Product Expert call failed (%s); asking the customer to try again", exc)
        return {
            "narratives": [],
            "satisfied": False,
            "still_consulting": True,
            "wants_new_search": False,
            "reply": (
                "Sorry, I had trouble pulling up options just now -- could you "
                "try that again in a moment?"
            ),
        }

    narratives = [pick.model_dump() for pick in result.top_picks] if result.top_picks else []

    return {
        "narratives": narratives,
        "satisfied": bool(result.satisfied and narratives),
        "still_consulting": bool(result.still_consulting),
        "wants_new_search": bool(result.wants_new_search),
        "reply": result.reply or "",
    }


__all__ = ["recommend"]
