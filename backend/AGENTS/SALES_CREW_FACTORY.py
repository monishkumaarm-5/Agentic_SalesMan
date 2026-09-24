"""
Shared builder for the per-category CrewAI sales crews (product expert ->
consumer psychologist -> storyteller -> sales consultant).

Built once per category *name* (any string from the live catalog -- see
DATABASE/SQL_CONNECTOR.py -- not a fixed Mobile/Laptop/Headphone enum) and
cached by WORKFLOW/ORCHE.py, so a brand-new category never needs a new
Python file the way MOBILE_SALES_AGENT.py/LAPTOP_SALES_AGENT.py/
HEADPHONE_SALES_AGENT.py used to.

This is also where task 1.2 ("the CrewAI setup isn't used as well as it
could be") and task 1.3 ("show the local store and company website") live:
  - every task now has a real `expected_output` describing the actual
    shape/content expected of it, instead of the generic placeholder
    "Short Crispy and punchy" every task used to share (CrewAI leans on
    expected_output to steer format -- a vague one gives the model little
    to aim for).
  - the product and sales agents both get a `get_company_info` /
    `find_nearby_stores` tool (TOOLS/company_tools.py) so the crew can
    ground a "where can I see this in person" / "what's your website"
    answer in real store data instead of staying silent or making
    something up.
  - the sales consultant can delegate back to the product expert
    (`allow_delegation=True`) if it needs to double-check something before
    finalizing the customer-facing answer, instead of just passing
    whatever the product expert said through unquestioned.

Uses %-style string formatting (not f-strings or str.format) to fill in the
category/product/company words, specifically so it never collides with the
"{user_request}" / "{{...}}" placeholder syntax that langchain's
PromptTemplate and CrewAI's own template substitution rely on in the same
text.
"""
import json
import re
from typing import Optional

from langchain_core.prompts import PromptTemplate
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

import config
from TOOLS.company_tools import get_company_info, list_store_locations
from TOOLS.product_tools import (
    ProductToolError,
    check_inventory,
    compare_products,
    get_current_price,
    search_products,
)

GEMINI_MODEL = "gemini/gemini-3.1-flash-lite"


def _make_llm() -> LLM:
    # CrewAI agents talk to Gemini through litellm, which -- for the
    # "gemini/..." model prefix -- reads GEMINI_API_KEY, not GOOGLE_API_KEY.
    # Building the LLM explicitly with api_key= sidesteps that env-var
    # mismatch entirely instead of relying on litellm's own lookup.
    # CREW_MODEL is optional -- most deployments never need to override
    # the default, so it's not in config.dummy.py, just supported.
    model_name = getattr(config, "CREW_MODEL", None) or GEMINI_MODEL
    return LLM(model=model_name, api_key=config.GOOGLE_API_KEY)


def _slug(word: str) -> str:
    """Sanitizes a (possibly multi-word) category noun like "Air
    Conditioner" into a tool/function-name-safe slug ("air_conditioner").
    Category names are free-form catalog data now (see
    DATABASE/SQL_CONNECTOR.py's module docstring), and CrewAI/Gemini
    function-calling tool names can't contain spaces or most punctuation."""
    slug = re.sub(r"[^a-z0-9]+", "_", word.strip().lower()).strip("_")
    return slug or "product"


def _build_product_tools(product_noun: str) -> list:
    """CrewAI tools scoped to one category (product_noun doubles as the
    TOOLS.product_tools/DATABASE `category` value -- so the agent never has
    to guess or pass it). These call TOOLS/product_tools.py directly,
    in-process -- the same functions MCP/server.py exposes to external MCP
    clients -- so the product agent can go beyond the pre-fetched RAG data
    when a request needs it (e.g. "compare the X and Y" or "is the X in
    stock"), without a second network hop for every chat turn.

    Every tool returns a JSON string (including on error) rather than
    raising, since a raised exception mid-crew is harder for the agent to
    recover from gracefully than an error message it can read and route
    around."""
    slug = _slug(product_noun)

    @tool(f"search_{slug}s")
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

    @tool(f"compare_{slug}s")
    def compare_tool(product_names: list) -> str:
        """Compare 2+ specific products by exact name, side by side. Use
        this when the customer names specific products to compare. Returns
        a JSON object with each product's data and which fields differ."""
        try:
            return json.dumps(compare_products(product_noun, product_names))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    @tool(f"check_{slug}_inventory")
    def inventory_tool(product_name: str) -> str:
        """Check whether a specific product (by exact name) is in stock."""
        try:
            return json.dumps(check_inventory(product_noun, product_name))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    @tool(f"get_{slug}_price")
    def price_tool(product_name: str) -> str:
        """Look up the current price of one specific product by exact
        name."""
        try:
            return json.dumps(get_current_price(product_noun, product_name))
        except ProductToolError as exc:
            return json.dumps({"error": str(exc)})

    return [search_tool, compare_tool, inventory_tool, price_tool]


def _build_company_tools() -> list:
    """Store/brand tools shared by every category's crew (task 1.3) --
    unlike _build_product_tools these aren't scoped to a product_noun, so
    they're plain functions rather than a per-category factory."""

    @tool("get_company_info")
    def company_info_tool() -> str:
        """Get this store's brand name, tagline, website and support phone
        number. Use when the customer asks who you are, for your website,
        or for general contact info -- never invent this, always call the
        tool."""
        return json.dumps(get_company_info())

    @tool("find_nearby_stores")
    def store_locator_tool(city: Optional[str] = None) -> str:
        """List this store's physical showroom locations (name, city,
        address, phone, hours), optionally filtered by city, so you can
        tell a customer where to see or buy a product in person. Only call
        this when the customer asks about physical stores/showrooms, or
        offline availability genuinely isn't already covered by the RAG
        data -- don't force a store mention into every answer."""
        return json.dumps(list_store_locations(city))

    return [company_info_tool, store_locator_tool]


def build_sales_crew(category: str, product_noun: str) -> Crew:
    """
    category: capitalized singular label used in agent roles, e.g. "Mobile",
        "Laptop", "Headphone", or any other category name the catalog has.
    product_noun: lowercase singular noun used in prose, e.g. "phone",
        "laptop", "headphone" -- its regular plural (+s) is used too.
    """
    plural = f"{product_noun}s"
    heading = product_noun.capitalize()
    company_name = getattr(config, "COMPANY_NAME", "Trein")
    slug = _slug(product_noun)
    words = {
        "category": category,
        "product": product_noun,
        "plural": plural,
        "company": company_name,
        # Tool names can't contain spaces (see _slug) -- %(slug)s/%(splural)s
        # are for literal tool-name mentions in prompts, always naming the
        # exact same tools _build_product_tools registers below;
        # %(product)s/%(plural)s stay for natural-language prose.
        "slug": slug,
        "splural": f"{slug}s",
    }

    product_prompt = PromptTemplate.from_template(
        """
You are a Senior %(category)s Product Expert at %(company)s.

Goal:
Analyze the customer's request and the retrieved RAG data to recommend the
best %(product)s(s) %(company)s actually carries.

Responsibilities:
- Understand customer requirements.
- Compare available %(plural)s.
- Recommend ONLY products present in the RAG data.
- Never invent specifications, prices or products not in the RAG data.
- Explain why the recommended %(product)s best matches the customer's needs.
- The RAG data is already ranked best-to-worst by our scoring engine. List
  your "top_picks" entries in that exact same order -- item #1 in the RAG
  data must be entry #1 in your output, and so on. Do not reorder products
  based on your own judgment.

Tools:
You have search/compare/inventory/price tools for %(plural)s, plus
get_company_info / find_nearby_stores for brand and store questions. The
RAG data below is already a scored shortlist for this request, so you
usually don't need the product tools -- but use compare_%(splural)s if the
customer names two or more specific products to compare,
check_%(slug)s_inventory if they ask about stock/availability,
get_%(slug)s_price if they ask for an exact current price, or
search_%(splural)s if the RAG data genuinely doesn't cover what they're
asking (e.g. a brand or price range not represented below). Only reach for
get_company_info / find_nearby_stores if the customer's request or the
sales consultant's follow-up genuinely needs it (e.g. "where can I see
this in person") -- don't force store info into every answer.

Return JSON exactly in this shape -- one entry per product, in the same
best-to-worst order as the RAG data below, using ONLY product names that
appear verbatim in the RAG data. Include up to 3 entries (fewer if the RAG
data lists fewer than 3 %(plural)s). Do not include price, discount, stock
or purchase-link fields -- those are attached automatically from the
catalog, never invented by you:

{{
    "top_picks": [
        {{
            "name": "<exact product name from RAG data>",
            "why_this": "<2-3 sentences on why this %(product)s is a strong pick>",
            "key_features": ["<verified feature>", "<verified feature>", "<verified feature>"],
            "why_suits_you": "<1-2 sentences tying it to the customer's stated needs, use case or budget>"
        }}
    ]
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
You are an Expert Consumer Psychologist working alongside %(company)s's
sales team.

Your job is to understand WHY the customer wants a %(product)s, using the
product expert's recommendation above plus the customer's own message --
never invent details about the customer that neither source supports.

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
You are a Professional Sales Storytelling Expert writing on behalf of
%(company)s.

Using the recommended %(product)s and customer psychology above,

Generate a short story that emotionally connects the customer with the
product.

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
Senior %(category)s Sales Consultant at %(company)s.

Instructions

1. Introduce your top recommended %(product)s -- this MUST be the #1 entry
   from the Product Expert's list above (the same product shown as the
   top pick card below your answer), never a different one from later in
   the list.
2. Explain why it matches the customer's needs.
3. Highlight only verified features.
4. Include the storytelling paragraph naturally.
5. Mention any available offers only if present in the RAG data.
6. End with one short, natural call-to-action sentence encouraging the
   customer to check it out -- do not use manipulative language or false
   scarcity.
7. Do not restate exact prices, discounts, stock counts or purchase links
   in prose, and do not add your own "Buy Now" / "Official Purchase
   Link" / "Available Online" section or heading -- a dedicated Buy Now
   card with that exact data (price, discount, units, online link,
   offline availability) is already shown separately for each of the top
   picks, right below your answer. Repeating it, or writing a placeholder
   like "link not available", only duplicates or contradicts that card.
8. Never invent links, prices or specifications.
9. Briefly note that a couple of strong alternatives are shown below, if
   the RAG data has more than one matching %(product)s.
10. If a detail that would sharpen a future recommendation was never
    stated (an exact budget, a brand preference, an intended use), you MAY
    end with one brief, natural follow-up question inviting the customer
    to share it -- only when it would genuinely help, and only in addition
    to (never instead of) the call-to-action from instruction 6.
11. If, and only if, the customer's request or context genuinely calls for
    it (e.g. they asked where to see or buy this in person, or about
    %(company)s itself), you may use get_company_info / find_nearby_stores
    and weave a brief, natural mention of the website or nearest store
    into the answer -- never force this into every response, and never
    invent a store or website that the tools didn't return.

Return Markdown, and stop after the Story section (or the optional
follow-up question from instruction 10) -- do not add any further
headings.

Format

# Recommended %(heading)s

Product Name

Why this %(product)s?

Key Features

Story (end this section with the one-sentence call-to-action from
instruction 6 -- do not label it "Buy Now" or add a link)
"""
        % {**words, "heading": heading}
    )

    llm = _make_llm()
    company_tools = _build_company_tools()

    product_agent = Agent(
        role=f"Senior {category} Product Expert",
        goal=f"Recommend the best {product_noun} {company_name} actually carries, from RAG data",
        backstory=(
            f"Expert in comparing {plural} using only verified product "
            f"information from {company_name}'s catalog."
        ),
        llm=llm,
        tools=_build_product_tools(product_noun) + company_tools,
        cache=True,
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
        goal=f"Generate the final sales response on behalf of {company_name}",
        backstory=(
            f"Combines technical knowledge with customer psychology to "
            f"represent {company_name} to the customer."
        ),
        llm=llm,
        tools=company_tools,
        # The last agent in the chain is the one actually answering the
        # customer -- letting it delegate back to the product expert (e.g.
        # to double-check a detail before finalizing) is a genuinely useful
        # extra capability that costs nothing when it isn't needed.
        allow_delegation=True,
        verbose=True,
    )

    product_task = Task(
        description=product_prompt.format(
            user_request="{user_request}", rag_data="{rag_data}"
        ),
        expected_output=(
            "A single JSON object with a top_picks array (1-3 entries, in "
            "the RAG data's exact best-to-worst order), each entry having "
            "name/why_this/key_features/why_suits_you exactly as specified "
            "above -- no prose outside the JSON, no product or spec not "
            "present verbatim in the RAG data."
        ),
        agent=product_agent,
    )

    psychology_task = Task(
        description=psychology_prompt.format(user_request="{user_request}"),
        expected_output=(
            "A single JSON object with customer_type, pain_points (a "
            "list), motivation, selling_strategy and urgency_level (Low/"
            "Medium/High), grounded in the customer's message and the "
            "product expert's recommendation -- no invented backstory "
            "about the customer."
        ),
        agent=psychology_agent,
        context=[product_task],
    )

    story_task = Task(
        description=story_prompt.format(),
        expected_output=(
            "A short (under 120 words) natural-language story in plain "
            "prose (not JSON) that connects the customer's stated need to "
            "the #1 recommended product, ending with one gentle "
            "call-to-action sentence -- no invented specs, prices or "
            "offers."
        ),
        agent=story_agent,
        context=[product_task, psychology_task],
    )

    sales_task = Task(
        description=sales_prompt.format(),
        expected_output=(
            "The final Markdown answer shown to the customer, following "
            "the Format section exactly (a '# Recommended "
            f"{heading}' heading, product name, why this "
            "%(product)s, key features, and the story's call-to-action), "
            "grounded only in the product expert's verified data, with no "
            "invented prices, links or stock claims, and no extra "
            "sections after the Story (and optional follow-up question)."
        ) % words,
        agent=sales_agent,
        context=[product_task, psychology_task, story_task],
    )

    return Crew(
        agents=[product_agent, psychology_agent, story_agent, sales_agent],
        tasks=[product_task, psychology_task, story_task, sales_task],
        process=Process.sequential,
        verbose=True,
    )
