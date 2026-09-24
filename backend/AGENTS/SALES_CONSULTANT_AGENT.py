"""
Sales Consultant Agent -- one structured LLM call replacing the old
CrewAI crew's Storytelling Expert + Sales Consultant tasks, PLUS what
WORKFLOW/ORCHE.py's `product_followup` node did in the CrewAI-based
pipeline (answering a doubt/comparison/opinion about an already-shown
product without re-running retrieval or the recommendation step).

Two distinct situations, one call, because the prompt tells them apart:

  1. First time for this product (`pitch_delivered` is false) -- write
     the full pitch: storytelling on why it suits them, plus a comparison
     of the top picks if there's more than one.

  2. Already pitched (`pitch_delivered` is true) -- this is the customer
     reacting. Answer a doubt/comparison/opinion question directly from
     the product(s) already shown (never invent anything not already in
     `product`), OR recognise they want something different and hand back
     to an earlier agent:
       - `next = "product_expert"` -- a different product in the SAME
         category ("show me something cheaper", "what else do you have").
       - `next = "business_need"`  -- a genuinely different category
         ("actually let's look at headphones instead").
       - `next = "done"`           -- answered their question, staying put.

This is also where "the ability to go to previous agents" lives -- the
graph takes whichever `next` this call returns as a real edge, so a
redirect can produce fresh results in the very same turn, no extra round
trip.
"""
import logging
from typing import Optional

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

logger = logging.getLogger("agentic_salesman.sales_consultant")

prompt_template = PromptTemplate.from_template(
    """
    Role: {category} Sales Consultant at {company_name}.

    Business need: {business_need}
    Customer psychology (motivation, pain points, urgency -- use this to
    frame the pitch, never state it back to the customer verbatim):
    {customer_psychology}

    Product(s) already selected for this customer:
    {product_summary}

    Conversation so far:
    {history}

    Customer's current message:
    {question}

    Has a pitch for this product already been shown to the customer in
    this thread? {pitch_delivered}

    If NOT yet shown (first time):
    - Write the full pitch. Introduce the #1 product, explain why it
      matches their need, weave in a short (under 120 words) natural story
      connecting it to their motivation, and -- only if there's more than
      one product above -- a brief comparison of the options. End with one
      gentle call-to-action question. Only verified features from the
      product summary above -- never invent specs, prices, links, or
      stock. Never restate exact prices or add a "Buy Now" section -- a
      dedicated purchase card is shown separately.
    - next = "done".

    If ALREADY shown (the customer is reacting):
    - COMPARE intent: If the customer asks to compare two or more
      products or brands (e.g. "compare Godrej and Samsung", "which is
      better X or Y", "pros and cons"), build a structured comparison
      table using ONLY verified specs from the product summary above.
      Format: a brief intro, then a markdown table with columns for each
      product and rows for each spec (price, brand, key features, rating,
      availability). End with a 1-2 sentence verdict tied to the
      customer's business need. NEVER invent specs not present above.
      next = "done".
    - If their message is a doubt or opinion about the product(s) above
      -- answer directly and only from what's in the product summary
      above. next = "done".
    - If they want a DIFFERENT BRAND in the SAME category (e.g. "show me
      Whirlpool", "what about LG", "I prefer Sony") -- acknowledge
      briefly. Set detected_brand to the brand they named.
      next = "product_expert".
    - If they want a different product in the SAME category for other
      reasons (cheaper, different specs, "what else do you have") --
      a brief acknowledgement, next = "product_expert".
    - If they want a genuinely different category -- a brief
      acknowledgement, next = "business_need".

    STRICT GROUNDING RULE: You may ONLY mention features, specs, and
    capabilities that are EXPLICITLY listed in the product summary above.
    If a spec is not mentioned (e.g. "4K support", "water resistance"),
    do NOT claim the product has it. Do NOT infer capabilities from
    other specs (e.g. do not say "108MP addresses 4K" unless 4K is
    explicitly stated). When unsure, say "that spec isn't listed in our
    catalog" rather than guessing.

    Output ONLY JSON matching the schema below.
    {{
        "answer": "",
        "next": "done",
        "detected_brand": null
    }}
    """
)


class SalesConsultantReply(BaseModel):
    answer: str = ""
    next: str = "done"
    detected_brand: Optional[str] = None


llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")
structured_llm = llm.with_structured_output(SalesConsultantReply)

_VALID_NEXT = {"done", "product_expert", "business_need"}


def _call_llm(
    question: str,
    category: str,
    business_need: dict,
    customer_psychology: dict,
    product_summary: str,
    history: str,
    pitch_delivered: bool,
    company_name: str,
) -> SalesConsultantReply:
    """Isolated so tests can monkeypatch just the LLM call."""
    chain = prompt_template | structured_llm
    return chain.invoke(
        {
            "question": question,
            "category": category,
            "business_need": business_need or {},
            "customer_psychology": customer_psychology or {},
            "product_summary": product_summary,
            "history": history or "(no prior conversation)",
            "pitch_delivered": "yes" if pitch_delivered else "no",
            "company_name": company_name,
        }
    )


def consult(
    question: str,
    category: str,
    business_need: Optional[dict] = None,
    customer_psychology: Optional[dict] = None,
    product_summary: str = "",
    history: str = "",
    pitch_delivered: bool = False,
    company_name: str = "Trein",
) -> dict:
    """Returns a plain dict (never raises): {"answer": str, "next": str}
    where next is one of "done" / "product_expert" / "business_need".
    Fails open to a polite apology and next="done" -- never leaves the
    customer with an empty answer, and never silently redirects them
    somewhere they didn't ask to go.
    """
    try:
        result = _call_llm(
            question, category, business_need or {}, customer_psychology or {},
            product_summary, history, pitch_delivered, company_name,
        )
    except Exception as exc:
        logger.warning("Sales Consultant call failed (%s); falling back to a plain apology", exc)
        return {
            "answer": (
                "Sorry, I had trouble putting that together just now -- "
                "could you try again in a moment?"
            ),
            "next": "done",
        }

    next_hop = result.next if result.next in _VALID_NEXT else "done"

    return {
        "answer": result.answer or "",
        "next": next_hop,
        "detected_brand": result.detected_brand or None,
    }


__all__ = ["consult"]
