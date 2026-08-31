"""
Shared builder for the per-category CrewAI sales crews (product expert ->
consumer psychologist -> storyteller -> sales consultant).

MOBILE_SALES_AGENT.py, LAPTOP_SALES_AGENT.py and HEADPHONE_SALES_AGENT.py
used to each hand-roll an almost identical copy of this crew, which is how
one of them ended up with a bug (a stray unused LangChain client) that the
other two didn't have. Centralizing it here means a fix only has to happen
once.

Uses %-style string formatting (not f-strings or str.format) to fill in the
category/product words, specifically so it never collides with the
"{user_request}" / "{{...}}" placeholder syntax that langchain's
PromptTemplate and CrewAI's own template substitution rely on in the same
text.
"""
import json
from typing import Optional

from langchain_core.prompts import PromptTemplate
from crewai import Agent, Crew, LLM, Task
from crewai.tools import tool

import config
from TOOLS.product_tools import (
    ProductToolError,
    check_inventory,
    compare_products,
    get_current_price,
    search_products,
)

GEMINI_MODEL = "gemini/gemini-3.5-flash-lite"


def _make_llm() -> LLM:
    # CrewAI agents talk to Gemini through litellm, which -- for the
    # "gemini/..." model prefix -- reads GEMINI_API_KEY, not GOOGLE_API_KEY.
    # Building the LLM explicitly with api_key= sidesteps that env-var
    # mismatch entirely instead of relying on litellm's own lookup.
    return LLM(model=GEMINI_MODEL, api_key=config.GOOGLE_API_KEY)


def _build_product_tools(product_noun: str) -> list:
    """CrewAI tools scoped to one category (product_noun doubles as the
    TOOLS.product_tools/DATABASE table key -- "phone"/"laptop"/"headphone"
    -- so the agent never has to guess or pass it). These call
    TOOLS/product_tools.py directly, in-process -- the same functions
    MCP/server.py exposes to external MCP clients -- so the product agent
    can go beyond the pre-fetched RAG data when a request needs it (e.g.
    "compare the X and Y" or "is the X in stock"), without a second
    network hop for every chat turn.

    Every tool returns a JSON string (including on error) rather than
    raising, since a raised exception mid-crew is harder for the agent to
    recover from gracefully than an error message it can read and route
    around."""

    @tool(f"search_{product_noun}s")
    def search_tool(
        max_price: Optional[float] = None,
        min_ram_gb: Optional[float] = None,
        min_storage_gb: Optional[float] = None,
        brand: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> str:
        """Search the catalog for more options than the pre-supplied RAG
        data, e.g. to widen a search or check a specific brand. All
        arguments are optional filters. Returns a JSON list of products."""
        try:
            return json.dumps(
                search_products(
                    product_noun,
                    max_price=max_price,
                    min_ram_gb=min_ram_gb,
                    min_storage_gb=min_storage_gb,
                    brand=brand,
                    keyword=keyword,
                    limit=5,
                )
            )
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    @tool(f"compare_{product_noun}s")
    def compare_tool(product_names: list) -> str:
        """Compare 2+ specific products by exact name, side by side. Use
        this when the customer names specific products to compare. Returns
        a JSON object with each product's data and which fields differ."""
        try:
            return json.dumps(compare_products(product_noun, product_names))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    @tool(f"check_{product_noun}_inventory")
    def inventory_tool(product_name: str) -> str:
        """Check whether a specific product (by exact name) is in stock."""
        try:
            return json.dumps(check_inventory(product_noun, product_name))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    @tool(f"get_{product_noun}_price")
    def price_tool(product_name: str) -> str:
        """Look up the current price of one specific product by exact
        name."""
        try:
            return json.dumps(get_current_price(product_noun, product_name))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    return [search_tool, compare_tool, inventory_tool, price_tool]


def build_sales_crew(category: str, product_noun: str) -> Crew:
    """
    category: capitalized singular label used in agent roles, e.g. "Mobile",
        "Laptop", "Headphone".
    product_noun: lowercase singular noun used in prose, e.g. "phone",
        "laptop", "headphone" -- its regular plural (+s) is used too.
    """
    plural = f"{product_noun}s"
    heading = product_noun.capitalize()
    words = {"category": category, "product": product_noun, "plural": plural}

    product_prompt = PromptTemplate.from_template(
        """
You are a Senior %(category)s Product Expert.

Goal:
Analyze the customer's request and the retrieved RAG data.

Responsibilities:
- Understand customer requirements.
- Compare available %(plural)s.
- Recommend ONLY products present in the RAG data.
- Never invent specifications.
- Explain why the recommended %(product)s best matches the customer's needs.

Tools:
You have search/compare/inventory/price tools for %(plural)s. The RAG data
below is already a scored shortlist for this request, so you usually don't
need them -- but use compare_%(plural)s if the customer names two or more
specific products to compare, check_%(product)s_inventory if they ask about
stock/availability, get_%(product)s_price if they ask for an exact current
price, or search_%(plural)s if the RAG data genuinely doesn't cover what
they're asking (e.g. a brand or price range not represented below).

Return JSON:

{{
    "recommended_product":"",
    "reason":"",
    "key_features":[],
    "buy_link":""
}}

User Request:
{user_request}

RAG Data:
{rag_data}
"""
        % words
    )

    psychology_prompt = PromptTemplate.from_template(
        """
You are an Expert Consumer Psychologist.

Your job is to understand WHY the customer wants a %(product)s.

Identify:
- Buying intent
- Pain points
- Emotional motivation
- Budget sensitivity
- Urgency
- Purchase confidence

Suggest the best persuasion strategy.

Return JSON:

{{
    "customer_type":"",
    "pain_points":[],
    "motivation":"",
    "selling_strategy":"",
    "urgency_level":"Low/Medium/High"
}}

User Request:
{user_request}
"""
        % words
    )

    story_prompt = PromptTemplate.from_template(
        """
You are a Professional Sales Storytelling Expert.

Using the recommended %(product)s and customer psychology,

Generate a short story that emotionally connects the customer with the product.

Rules:
- Keep under 120 words.
- Be natural.
- Do NOT exaggerate.
- Focus on solving the customer's problem.
- End with a gentle call to action.
"""
        % words
    )

    sales_prompt = PromptTemplate.from_template(
        """
Role:
Senior %(category)s Sales Consultant.

Instructions

1. Introduce the recommended %(product)s.
2. Explain why it matches the customer's needs.
3. Highlight only verified features.
4. Include the storytelling paragraph naturally.
5. Mention any available offers only if present in the RAG data.
6. Encourage the customer to purchase without using manipulative or false scarcity.
7. Include the official purchase link from the RAG data.
8. Never invent links or specifications.

Return Markdown.

Format

# Recommended %(heading)s

Product Name

Why this %(product)s?

Key Features

Story

Buy Now

Official Purchase Link
"""
        % {**words, "heading": heading}
    )

    llm = _make_llm()

    product_agent = Agent(
        role=f"Senior {category} Product Expert",
        goal=f"Recommend the best {product_noun} from RAG data",
        backstory=f"Expert in comparing {plural} using only verified product information.",
        llm=llm,
        tools=_build_product_tools(product_noun),
        verbose=True,
    )

    psychology_agent = Agent(
        role="Consumer Psychologist",
        goal="Understand customer buying intent",
        backstory="Specialist in consumer psychology and purchasing behavior.",
        llm=llm,
        verbose=True,
    )

    story_agent = Agent(
        role="Storytelling Expert",
        goal="Create emotional product stories",
        backstory="Creates engaging but truthful stories for customers.",
        llm=llm,
        verbose=True,
    )

    sales_agent = Agent(
        role=f"{category} Sales Consultant",
        goal="Generate the final sales response",
        backstory="Combines technical knowledge with customer psychology.",
        llm=llm,
        verbose=True,
    )

    product_task = Task(
        description=product_prompt.format(
            user_request="{user_request}", rag_data="{rag_data}"
        ),
        expected_output="Short Crispy and punchy",
        agent=product_agent,
    )

    psychology_task = Task(
        description=psychology_prompt.format(user_request="{user_request}"),
        expected_output="Short Crispy and punchy",
        agent=psychology_agent,
        context=[product_task],
    )

    story_task = Task(
        description=story_prompt.format(),
        expected_output="Short Crispy and punchy",
        agent=story_agent,
        context=[product_task, psychology_task],
    )

    sales_task = Task(
        description=sales_prompt.format(),
        expected_output="Short Crispy and punchy for chatting user",
        agent=sales_agent,
        context=[product_task, psychology_task, story_task],
    )

    return Crew(
        agents=[product_agent, psychology_agent, story_agent, sales_agent],
        tasks=[product_task, psychology_task, story_task, sales_task],
        verbose=True,
    )
