"""
Advisor agent -- answers questions about specific products (specs,
reviews, comparisons, "which is better for me") strictly from catalog
data, and tells the UI which products to show or compare.
"""
from pydantic import BaseModel, Field

from app.agents.llm import structured_call


class AdvisorOutput(BaseModel):
    message: str = Field(description="The chat reply in Markdown")
    compare_products: list[str] = Field(
        default_factory=list, description="Exact names to show side by side when the answer is a comparison")
    show_products: list[str] = Field(
        default_factory=list, description="Exact names of products the answer is about, to show as cards")
    suggestions: list[str] = Field(default_factory=list)


SYSTEM = """You are {company}'s product expert, helping a customer decide between specific products.

Answer the customer's latest message using ONLY the PRODUCT DATA below.
- Be direct: answer the question first, then add the context that matters for their needs.
- For comparisons, include a compact Markdown table (at most 6 rows of the specs that actually differ or matter), then a clear verdict for this customer.
- If the data doesn't say (e.g. warranty, water resistance), say that it isn't listed rather than guessing, and mention what is known.
- If they sound ready to buy, point them to the buy button or the showroom listed on the product card.
- Keep it under 180 words. No links.

"compare_products": exact names when your answer compares products (the app shows a side-by-side view). "show_products": exact names of the products your answer is about (the app shows their cards); may be empty.
"suggestions": 2-4 short next messages in the customer's voice.
Reply in the customer's language."""

USER = """CUSTOMER PROFILE
{profile}

CONVERSATION SO FAR
{history}

CUSTOMER'S LATEST MESSAGE
{message}

PRODUCT DATA
{products}"""


def advise(variables: dict) -> AdvisorOutput:
    return structured_call(AdvisorOutput, SYSTEM, USER, variables)
