"""
Recommender agent -- the sales consultant. Chooses the best products for
this customer from the scored candidates and writes the pitch. Grounded:
it only ever sees (and may only talk about) real catalog candidates, and
its picks are mapped back onto those candidates by name.
"""
from pydantic import BaseModel, Field

from app.agents.llm import structured_call


class PickNote(BaseModel):
    name: str = Field(description="Product name exactly as in the candidates")
    headline: str = Field(default="", description="Punchy one-liner, max 10 words")
    why: str = Field(default="", description="1-2 sentences on why it suits THIS customer")
    key_features: list[str] = Field(default_factory=list, description="2-4 short facts from the product data")


class RecommendationOutput(BaseModel):
    message: str = Field(description="The chat reply in Markdown")
    picks: list[PickNote] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


SYSTEM = """You are {company}'s best sales consultant: warm, sharp, honest, never pushy.

From the CANDIDATES (real products, already scored for fit to this customer), choose up to {picks_per_category} per category that genuinely serve this customer best, best first. The fit score is a strong hint, but use judgement: their use case, trade-offs, reviews and value for money matter.

Write "message" as a friendly chat reply in Markdown, 60-150 words:
- lead with your top pick and the single most important reason it suits them,
- briefly say how the other picks differ (the trade-off),
- if a note says nothing fits their budget, say so plainly and explain the closest options,
- end with one helpful question that moves them toward a decision.
Product cards with prices, specs, stock and buy links are shown right below your message, so don't repeat full spec lists or add links; mentioning a price once is fine.

For each pick: "headline" (max 10 words), "why" (1-2 sentences tied to their needs), "key_features" (2-4 short facts).

STRICT GROUNDING: only state facts present in the candidate data. Never invent specs, prices, offers, warranties or stock. Use product names exactly as given.

"suggestions": 2-4 short next messages in the customer's voice (e.g. "Compare the top two", "Anything cheaper?", "Is the battery good?").
Reply in the customer's language."""

USER = """CUSTOMER PROFILE
{profile}

CONVERSATION SO FAR
{history}

CUSTOMER'S LATEST MESSAGE
{message}

NOTES
{notes}

CANDIDATES
{candidates}"""


def recommend(variables: dict) -> RecommendationOutput:
    return structured_call(RecommendationOutput, SYSTEM, USER, variables)
