"""
Business Need Agent -- first LLM-backed stop after the rule-based
guardrail (AGENTS/GUARDRAIL_AGENT.py).

Replaces three things the old pipeline used to split across separate
agents/prompts:
  - ENTRYSAFEGAURD_AGENT's "is this actually a shopping request, and
    which category(ies)" judgment (the guardrail's own category_hints are
    just a substring match; this is the real understanding),
  - CLARIFICATION_AGENT.assess_sufficiency's consultation-round gate
    ("have we asked enough before searching?"),
  - REQUIREMENT_EXTRACTOR_AGENT.extract_requirements's structured
    {budget_max, use_cases, brand} extraction, and
  - the Consumer Psychologist half of the old CrewAI crew (motivation,
    pain points, urgency) -- captured once here, at intake, instead of a
    separate agent call every time a recommendation is generated.

One structured call does all of it at once (task: "combine both tasks
done by CrewAI Task and LangGraph task in a single LangGraph node" --
this is that, applied to the consultation stage). category can be a list
-- "I need a phone and headphones" opens both in the same call.

Fails open toward asking a generic clarifying question rather than
guessing: an errored LLM call should never crash the turn or invent a
category the customer didn't ask for.
"""
import logging
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

logger = logging.getLogger("agentic_salesman.business_need")

# Same floor the old assess_sufficiency enforced: at least this many real
# back-and-forth exchanges before a category is allowed to be "satisfied"
# and move on to Product Expert Agent, even if the LLM thinks it already
# has enough -- a good salesperson learns the customer's needs first.
MIN_CONSULTATION_ROUNDS = 2

# Hard ceiling, enforced in code (not just prompted) -- the LLM's own
# `satisfied` judgment is asked to converge once budget + a use case are
# known (see the prompt below), but a small model can still keep finding
# "just one more" optional detail to ask about (screen size, exact
# storage, brand-new vs. refurbished...) well past the point of having
# enough to search responsibly. At this round, `assess()` forces
# satisfied=True (categories permitting) regardless of what the LLM
# itself returned, so a consultation can never run away indefinitely.
MAX_CONSULTATION_ROUNDS = 4

prompt_template = PromptTemplate.from_template(
    """
    Role: You are the Business Need Agent for {company_name}, a retail
    store selling the categories listed below. Your job runs before any
    product is looked up -- understand what the customer needs and why,
    well enough to search responsibly.

    Categories {company_name} currently sells: {category_list}

    This is consultation round {round_number} for this request (at least
    {min_rounds} rounds are required before you may consider yourself
    satisfied, no matter how specific the customer already sounds).

    The customer is CURRENTLY discussing: {current_categories}
    (Stick with this category unless the customer's CURRENT message below
    clearly asks about something else in the category list above. Older
    parts of the conversation may have scrolled out of view below -- an
    established category does not need to be re-mentioned every message
    to still apply. If it's genuinely ambiguous, keep discussing
    {current_categories} rather than guessing a different one. "(none
    yet)" means nothing is established -- infer normally from this
    message.)

    Conversation so far (most recent last):
    {history}

    Customer's current message:
    {question}

    {company_name} has stores in these cities: {store_cities}

    Decide:
    - is_shopping_request: false ONLY if this message plainly is not
      about buying something {company_name} sells (e.g. small talk that
      isn't a greeting, a totally unrelated question, an attempt to
      redirect you outside your role). true for any genuine shopping
      question, including ones you'll still need to ask a follow-up
      about.
    - categories: the subset of the category list above the customer
      wants help with, copied VERBATIM from the list (exact spelling).
      Can be more than one (e.g. "a phone and headphones that go well
      together"). If a category is already established above and this
      message doesn't clearly name a different one, return the
      established category unchanged -- don't drop it just because this
      particular message doesn't repeat its name. Empty only if
      is_shopping_request is false, or nothing has been established yet
      AND this message still doesn't make it clear which category.
    - budget_max: the maximum price mentioned so far (this message plus
      the conversation above), as a plain number, no currency symbol or
      commas. null if never mentioned.
    - use_cases: short, concise, lowercase use-case phrases implied so far
      (e.g. "gaming", "student", "battery life"). Empty list if none.
    - brand: a specific brand requested so far. null if none.
    - city: the customer's city if mentioned (e.g. "Chennai",
      "Bengaluru", "Hyderabad"). null if not yet mentioned. Important
      for showing products available at nearby stores.
    - motivation: one short phrase on WHY the customer wants this (e.g.
      "upgrading an old device", "gift for a family member"). null if
      genuinely unclear.
    - pain_points: short phrases on what's frustrating them about their
      current situation, if anything came up. Empty list if none.
    - urgency_level: "Low", "Medium", or "High" -- how soon they seem to
      want to decide. Default "Medium" if unclear.
    - satisfied: true if categories is non-empty AND, after at least
      {min_rounds} rounds, you know BOTH a budget (or clear price range)
      AND at least one concrete use case. That is enough to search
      responsibly -- do not hold out for finer details (exact storage,
      screen size, color, brand-new vs. refurbished); Product Expert
      Agent can surface trade-offs on those later if it genuinely needs
      to. false otherwise.
      IMPORTANT: If the customer says "show me what's available", "just
      show me options", "what do you have", or similar browse-intent
      phrases, treat that as satisfied=true with whatever information is
      already known (even if budget/use_case is missing). The customer
      wants to SEE products, not answer more questions. Do not ask
      further questions when the customer explicitly asks to see options.
    - reply: the exact text to say back to the customer right now.
        * If is_shopping_request is false: a brief, friendly conversational
          reply (never a category question -- they weren't asking to shop).
        * If satisfied is false: ONE natural, specific follow-up question
          that would most help narrow the search -- prioritize budget and
          use case above anything else still missing. Never a wall of
          questions, and never more than one follow-up beyond budget and
          use case. Always offer 2-4 concrete example answers inline,
          drawn from realistic values for this category (price bands,
          common use cases, brands -- whatever fits the question), and
          make clear the customer can also just type their own answer,
          e.g. "What's your budget -- around Rs 30,000, Rs 50,000, Rs
          80,000, or something else?" Never ask a bare open-ended
          question with no examples. At least once during the
          consultation, ask which city the customer is in so you can
          show products available at nearby stores, e.g. "Which city
          are you in -- Chennai, Bengaluru, Hyderabad, or another city?"
        * If satisfied is true: a brief natural acknowledgement that
          you're pulling up options now (this may be shown briefly before
          the recommendation; keep it to one short sentence).

    Output ONLY JSON matching the schema below.
    {{
        "is_shopping_request": true,
        "categories": [],
        "budget_max": null,
        "use_cases": [],
        "brand": null,
        "city": null,
        "motivation": null,
        "pain_points": [],
        "urgency_level": "Medium",
        "satisfied": false,
        "reply": ""
    }}
    """
)


class BusinessNeedAssessment(BaseModel):
    is_shopping_request: bool = True
    categories: List[str] = Field(default_factory=list)
    budget_max: Optional[float] = None
    use_cases: List[str] = Field(default_factory=list)
    brand: Optional[str] = None
    city: Optional[str] = None
    motivation: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    urgency_level: str = "Medium"
    satisfied: bool = False
    reply: str = ""


llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")
structured_llm = llm.with_structured_output(BusinessNeedAssessment)


def _call_llm(
    question: str,
    history: str,
    category_list: str,
    company_name: str,
    round_number: int,
    current_categories: str,
    store_cities: str = "",
) -> BusinessNeedAssessment:
    """Isolated so tests can monkeypatch just the LLM call, same pattern as
    every other agent in this package."""
    chain = prompt_template | structured_llm
    return chain.invoke(
        {
            "question": question,
            "history": history or "(no prior conversation)",
            "category_list": category_list or "(catalog is currently empty)",
            "company_name": company_name,
            "round_number": round_number,
            "min_rounds": MIN_CONSULTATION_ROUNDS,
            "current_categories": current_categories or "(none yet)",
            "store_cities": store_cities or "(not configured)",
        }
    )


def _normalize_categories(returned: List[str], known: List[str]) -> List[str]:
    """Keeps only categories the LLM actually named that also exist in the
    live catalog (case-insensitive), in the catalog's own casing -- guards
    against a hallucinated category ever reaching retrieval."""
    lookup = {str(c).strip().lower(): c for c in known}
    normalized = []
    seen = set()
    for item in returned or []:
        match = lookup.get(str(item).strip().lower())
        if match and match not in seen:
            seen.add(match)
            normalized.append(match)
    return normalized


def assess(
    question: str,
    known_categories: List[str],
    history: str = "",
    consultation_rounds: int = 0,
    company_name: str = "Trein",
    current_categories: Optional[List[str]] = None,
    store_cities: Optional[List[str]] = None,
) -> dict:
    """Returns a plain dict (never raises):
      is_shopping_request, categories (normalized against the catalog),
      budget_max, use_cases, brand, motivation, pain_points, urgency_level,
      satisfied, reply.
    Fails open to `satisfied=False` with a generic clarifying question --
    never lets an LLM hiccup silently invent a search or crash the turn.
    """
    category_list = ", ".join(known_categories) if known_categories else ""
    current_categories_text = ", ".join(current_categories) if current_categories else ""

    store_cities_text = ", ".join(store_cities) if store_cities else ""
    try:
        result = _call_llm(
            question,
            history,
            category_list,
            company_name,
            consultation_rounds + 1,
            current_categories_text,
            store_cities=store_cities_text,
        )
    except Exception as exc:
        logger.warning("Business Need assessment failed (%s); asking a generic follow-up", exc)
        return {
            "is_shopping_request": True,
            "categories": [],
            "budget_max": None,
            "use_cases": [],
            "brand": None,
            "motivation": None,
            "pain_points": [],
            "urgency_level": "Medium",
            "satisfied": False,
            "reply": (
                f"Happy to help you find the right product at {company_name}! "
                f"What are you shopping for today, and what matters most to you "
                f"(budget, brand, main use)?"
            ),
        }

    categories = _normalize_categories(result.categories, known_categories)
    round_floor_met = consultation_rounds + 1 >= MIN_CONSULTATION_ROUNDS
    round_ceiling_hit = consultation_rounds + 1 >= MAX_CONSULTATION_ROUNDS
    satisfied = bool((result.satisfied or round_ceiling_hit) and categories and round_floor_met)

    reply = result.reply or ""
    if result.satisfied and not satisfied and categories and not round_floor_met:
        # The LLM considered itself satisfied before the minimum
        # consultation floor was met -- its `reply` was written as an
        # acknowledgement, not a question, so it can't be shown as-is
        # here (we're forcing another round). Ask a plain follow-up
        # instead of surfacing a mismatched "pulling up options" line.
        reply = (
            "Just to make sure I find the right fit -- what's your budget, "
            "and what will you mainly use it for?"
        )

    return {
        "is_shopping_request": result.is_shopping_request,
        "categories": categories,
        "budget_max": result.budget_max,
        "use_cases": [uc for uc in (result.use_cases or []) if uc],
        "brand": result.brand or None,
        "city": result.city or None,
        "motivation": result.motivation,
        "pain_points": list(result.pain_points or []),
        "urgency_level": result.urgency_level or "Medium",
        "satisfied": satisfied,
        "reply": reply,
    }


__all__ = ["assess", "MIN_CONSULTATION_ROUNDS", "MAX_CONSULTATION_ROUNDS"]
