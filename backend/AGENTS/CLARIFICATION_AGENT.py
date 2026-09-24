"""
Pre-crew consultation & clarification agent.

Consultation-first approach: Instead of immediately recommending products,
the agent asks at least MIN_CONSULTATION_ROUNDS clarifying questions to
understand what the customer actually needs before making recommendations.

Split into two entry points so WORKFLOW/ORCHE.py can gate the Chroma
vector-DB call itself, not just the downstream CrewAI crew:

  assess_sufficiency() -- called BEFORE hybrid_search(). Covers what used
    to be called "layer 2" and "layer 3":
      2. Consultation round check: if fewer than MIN_CONSULTATION_ROUNDS
         meaningful exchanges have happened for this category, ALWAYS ask
         a targeted question -- even if the request seems specific
         enough. A good salesperson learns the customer's needs before
         pitching.
      3. Past the minimum rounds, an LLM judgment call on whether the
         customer's stated requirements are specific enough to be worth
         searching the catalog for at all.
    Neither layer needs retrieval results -- both only look at what the
    customer has said so far -- which is what lets this run before
    hybrid_search and skip it entirely when the answer is "not yet".

  assess_result_quality() -- called AFTER hybrid_search(), only when
    assess_sufficiency() said there was enough to search for. Covers what
    used to be "layer 1": zero matching candidates always means "ask" --
    there is nothing groundable to recommend from, no matter how specific
    the customer's request was.

assess_clarity() is kept as a thin wrapper composing both, for any other
caller that still wants the old all-in-one, post-retrieval check.

Fails open throughout: an errored LLM call means "don't block", not
"always ask".
"""
import logging
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from AGENTS.llm import build_llm
from pydantic import BaseModel, Field

logger = logging.getLogger("agentic_salesman.clarification")

# Minimum number of clarifying exchanges before allowing a recommendation
# (and, therefore, before the vector DB is ever queried for a fresh
# category -- see assess_sufficiency). The agent will ask at least this
# many questions to understand the customer's needs before searching.
MIN_CONSULTATION_ROUNDS = 2

# ---------- Prompt for consultation questions (rounds 1 & 2) ----------

consultation_prompt_template = PromptTemplate.from_template(
    """
    Role: You are a smart, friendly sales consultant for {company_name}.
    Your job is to understand the customer BEFORE recommending anything.

    The customer is interested in: {product_noun}
    This is consultation round {round_number} of {min_rounds}.

    Customer's message:
    {question}

    Conversation history:
    {history}

    Requirements gathered so far:
    {requirements}

    Your task: Ask ONE focused, helpful question to better understand
    what the customer needs. Do NOT recommend any product yet.

    Guidelines for what to ask based on the round:
    - Round 1: Focus on PRIMARY USE CASE and BUDGET.
      Examples: "What will you mainly use this for -- gaming, work,
      everyday use?" or "Do you have a budget range in mind?"
    - Round 2: Focus on SPECIFIC PREFERENCES based on what they've
      already told you.
      Examples: If they said gaming, ask about screen size or
      performance preferences. If they said budget, ask about brand
      preference or must-have features.

    Keep it conversational and SHORT (1-2 sentences). Do NOT list
    multiple questions -- ask just ONE clear question. Show that you
    understood what they already said.

    Output ONLY JSON:
    {{
        "clarifying_question": "your single question here",
        "missing": ["what_info_is_still_needed"]
    }}
    """
)

# ---------- Prompt for pre-retrieval sufficiency (after min rounds) ----

sufficiency_prompt_template = PromptTemplate.from_template(
    """
    Role: Pre-sales clarity checker for {company_name}'s e-commerce sales
    agent.
    Task: The customer has already been consulted with {round_number}
    question(s). Decide whether they have given enough information to be
    worth searching the product catalog for -- i.e. is there a genuine,
    specific need here (a use case, a budget, a brand, a must-have
    feature), or is this still too vague to search meaningfully?

    Since the customer has already answered {round_number} question(s),
    lean toward sufficient=true -- do not over-interrogate. Only ask
    again if a critical piece is genuinely missing (e.g. they want a
    phone but never mentioned budget, use case, or brand at all).

    Customer's latest message:
    {question}

    Conversation history:
    {history}

    Extracted requirements so far:
    {requirements}

    Output ONLY JSON:
    {{
        "sufficient": true,
        "clarifying_question": null,
        "missing": []
    }}
    """
)


# ---------- Prompt for follow-up vs. fresh-request routing -------------

followup_prompt_template = PromptTemplate.from_template(
    """
    Role: You are deciding how to route a customer's message for
    {company_name}'s shopping assistant.

    The customer was just shown these specific product(s):
    {product_names}

    Their new message:
    {question}

    Recent conversation:
    {history}

    Decide: is this message a FOLLOW-UP about the product(s) already
    shown -- an opinion, a doubt, a question about a spec or feature, a
    comparison between the shown products, or a general "what do you
    think" -- something answerable using what has already been shown,
    with NO new product search needed?

    Or is it a FRESH REQUIREMENT -- a new or changed budget, a different
    feature, a different brand, or anything else that means the catalog
    should be searched again, possibly for a different product?

    When genuinely unsure, prefer FRESH REQUIREMENT (search again) --
    it is safer to re-search than to answer from data that may no longer
    fit what the customer wants.

    Output ONLY JSON:
    {{
        "is_followup": true
    }}
    """
)


class FollowupIntent(BaseModel):
    is_followup: bool


class ConsultationQuestion(BaseModel):
    clarifying_question: str
    missing: List[str] = Field(default_factory=list)


class ClarityCheck(BaseModel):
    sufficient: bool
    clarifying_question: Optional[str] = None
    missing: List[str] = Field(default_factory=list)


llm = build_llm()
consultation_llm = llm.with_structured_output(ConsultationQuestion)
structured_llm = llm.with_structured_output(ClarityCheck)
followup_llm = llm.with_structured_output(FollowupIntent)


def _call_consultation_llm(
    question: str,
    history: str,
    requirements_text: str,
    product_noun: str,
    company_name: str,
    round_number: int,
) -> ConsultationQuestion:
    chain = consultation_prompt_template | consultation_llm
    return chain.invoke(
        {
            "question": question,
            "history": history or "(no prior conversation)",
            "requirements": requirements_text,
            "product_noun": product_noun,
            "company_name": company_name,
            "round_number": round_number,
            "min_rounds": MIN_CONSULTATION_ROUNDS,
        }
    )


def _call_sufficiency_llm(
    question: str,
    history: str,
    requirements_text: str,
    company_name: str,
    round_number: int,
) -> ClarityCheck:
    chain = sufficiency_prompt_template | structured_llm
    return chain.invoke(
        {
            "question": question,
            "history": history or "(no prior conversation)",
            "requirements": requirements_text,
            "company_name": company_name,
            "round_number": round_number,
        }
    )


def _call_followup_llm(
    question: str,
    history: str,
    product_names: List[str],
    company_name: str,
) -> FollowupIntent:
    chain = followup_prompt_template | followup_llm
    return chain.invoke(
        {
            "question": question,
            "history": history or "(no prior conversation)",
            "product_names": ", ".join(product_names) if product_names else "(none)",
            "company_name": company_name,
        }
    )


def assess_followup_intent(
    question: str,
    product_names: Optional[List[str]] = None,
    history: str = "",
    company_name: str = "Trein",
) -> dict:
    """Distinguishes a doubt/opinion/comparison question about the
    ALREADY-shown product(s) from a fresh requirement that should trigger
    a new catalog search. Only meaningful once a product has actually
    been shown for the active category -- WORKFLOW/ORCHE.py's
    entry_gaurd_agent only calls this when state["product"] is already
    set, so `product_names` empty here just means "nothing to be a
    follow-up about yet".

    Fails open toward the SAFER of the two outcomes: an errored LLM call,
    or no product_names at all, is treated as "not a follow-up", i.e.
    falls back to the existing search pipeline rather than risk answering
    from stale/no data."""
    if not product_names:
        return {"is_followup": False}

    try:
        result = _call_followup_llm(
            question, history, product_names, company_name,
        )
    except Exception as exc:
        logger.warning(
            "Follow-up intent check failed (%s); treating as a fresh request", exc,
        )
        return {"is_followup": False}

    return {"is_followup": bool(result.is_followup)}


def _no_matches_question(product_noun: str, company_name: str) -> str:
    return (
        f"I couldn't find a {product_noun} matching that in our {company_name} "
        f"catalog right now. Could you share a rough budget, a brand you like, "
        f"or what you'll mainly use it for? I can also check what's available "
        f"at one of our stores if that's easier."
    )


def _default_consultation_question(product_noun: str, round_number: int) -> str:
    if round_number <= 1:
        return (
            f"I'd love to help you find the perfect {product_noun}! "
            f"What will you mainly use it for, and do you have a budget range in mind?"
        )
    return (
        f"Thanks for sharing that! Any particular brand preference or "
        f"must-have features you're looking for in a {product_noun}?"
    )


def assess_sufficiency(
    question: str,
    product_noun: str,
    requirements: Optional[dict] = None,
    company_name: str = "Trein",
    consultation_rounds: int = 0,
    history: str = "",
) -> dict:
    """Pre-retrieval gate: is there enough customer-stated information to
    be worth calling the vector DB for at all? Returns
    {"needs_clarification": bool, "question": str|None, "missing": [...]}.
    Never raises -- fails open (an LLM error means "go ahead and
    search", not "keep asking")."""
    requirements_text = str(requirements or {})

    # Consultation-first -- must ask at least MIN_CONSULTATION_ROUNDS
    # questions before searching, regardless of how specific the request
    # seems.
    if consultation_rounds < MIN_CONSULTATION_ROUNDS:
        round_number = consultation_rounds + 1
        logger.info(
            "Consultation round %d/%d for %s -- asking before searching",
            round_number, MIN_CONSULTATION_ROUNDS, product_noun,
        )
        try:
            result = _call_consultation_llm(
                question, history, requirements_text,
                product_noun, company_name, round_number,
            )
            return {
                "needs_clarification": True,
                "question": result.clarifying_question or _default_consultation_question(
                    product_noun, round_number
                ),
                "missing": list(result.missing or []),
            }
        except Exception as exc:
            logger.warning("Consultation LLM failed (%s); using default question", exc)
            return {
                "needs_clarification": True,
                "question": _default_consultation_question(product_noun, round_number),
                "missing": ["consultation_llm_error"],
            }

    # Past minimum rounds -- LLM decides if the stated requirements are
    # specific enough to search for.
    try:
        result = _call_sufficiency_llm(
            question, history, requirements_text, company_name, consultation_rounds,
        )
    except Exception as exc:
        logger.warning("Sufficiency check failed (%s); proceeding to search", exc)
        return {"needs_clarification": False, "question": None, "missing": []}

    if result.sufficient:
        return {"needs_clarification": False, "question": None, "missing": []}

    return {
        "needs_clarification": True,
        "question": result.clarifying_question or _default_consultation_question(
            product_noun, consultation_rounds + 1
        ),
        "missing": list(result.missing or []),
    }


def assess_result_quality(
    candidates: Optional[list],
    product_noun: str,
    company_name: str = "Trein",
) -> dict:
    """Post-retrieval gate: called only when assess_sufficiency() already
    said there was enough to search for. Zero matching candidates always
    means "ask" -- there is nothing groundable to recommend from, no
    matter how specific the request was. This is a deterministic,
    no-LLM-call check. Returns the same {"needs_clarification", "question",
    "missing"} shape as assess_sufficiency()."""
    if not candidates:
        return {
            "needs_clarification": True,
            "question": _no_matches_question(product_noun, company_name),
            "missing": ["matching_products"],
        }
    return {"needs_clarification": False, "question": None, "missing": []}


def assess_clarity(
    question: str,
    product_noun: str,
    requirements: Optional[dict] = None,
    candidates: Optional[list] = None,
    company_name: str = "Trein",
    consultation_rounds: int = 0,
    history: str = "",
) -> dict:
    """Backward-compatible all-in-one check: runs assess_result_quality()
    first (it's free -- no LLM call), then assess_sufficiency() if there
    were candidates to consider. Prefer calling the two functions
    directly and gating retrieval itself -- see WORKFLOW/ORCHE.py's
    _run_one_category -- this wrapper exists for callers that already
    have candidates in hand and want the original single-call shape."""
    result_quality = assess_result_quality(candidates, product_noun, company_name)
    if result_quality["needs_clarification"]:
        return result_quality

    return assess_sufficiency(
        question,
        product_noun,
        requirements=requirements,
        company_name=company_name,
        consultation_rounds=consultation_rounds,
        history=history,
    )


__all__ = [
    "assess_clarity",
    "assess_sufficiency",
    "assess_result_quality",
    "assess_followup_intent",
    "MIN_CONSULTATION_ROUNDS",
]
