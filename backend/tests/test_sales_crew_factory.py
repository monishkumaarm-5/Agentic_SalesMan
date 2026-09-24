"""
Tests for AGENTS/SALES_CREW_FACTORY.py -- the CrewAI tool adapters
(_build_product_tools, _build_company_tools) and the crew/task wiring in
build_sales_crew. Crew/Agent/Task construction itself is exercised
directly (building a crew is cheap -- Agent/Task/Crew are just Python
objects; nothing calls the LLM until .kickoff()), no mocking needed for
that part.
"""
import json
from unittest.mock import patch

from crewai import Process

from AGENTS.SALES_CREW_FACTORY import (
    _build_company_tools,
    _build_product_tools,
    _slug,
    build_sales_crew,
)


def test_build_product_tools_returns_four_scoped_tools():
    tools = _build_product_tools("laptop")
    names = {t.name for t in tools}
    assert names == {"search_laptops", "compare_laptops", "check_laptop_inventory", "get_laptop_price"}


def test_slug_sanitizes_multiword_categories_for_tool_names():
    # Category names are free-form catalog data now (any string in the
    # `products` table's `category` column -- see DATABASE/SQL_CONNECTOR.py),
    # and CrewAI/Gemini function-calling tool names can't contain spaces or
    # punctuation, so a category like "Air Conditioner" must slugify
    # cleanly rather than producing an invalid tool name.
    assert _slug("Air Conditioner") == "air_conditioner"
    assert _slug("  Mixer Grinder!  ") == "mixer_grinder"
    assert _slug("laptop") == "laptop"
    assert _slug("") == "product"
    assert _slug("   ") == "product"


def test_build_product_tools_scopes_multiword_category_tool_names():
    tools = {t.name for t in _build_product_tools("air conditioner")}
    assert tools == {
        "search_air_conditioners",
        "compare_air_conditioners",
        "check_air_conditioner_inventory",
        "get_air_conditioner_price",
    }


def test_search_tool_delegates_to_search_products():
    tools = {t.name: t for t in _build_product_tools("laptop")}
    with patch("AGENTS.SALES_CREW_FACTORY.search_products", return_value=[{"name": "X"}]) as mock_fn:
        result = tools["search_laptops"].func(max_price=80000)
    mock_fn.assert_called_once_with(
        "laptop", max_price=80000, min_ram_gb=None, min_storage_gb=None, brand=None, keyword=None, limit=5
    )
    assert json.loads(result) == [{"name": "X"}]


def test_compare_tool_returns_json_error_instead_of_raising():
    from TOOLS.product_tools import ProductToolError

    tools = {t.name: t for t in _build_product_tools("laptop")}
    with patch("AGENTS.SALES_CREW_FACTORY.compare_products", side_effect=ProductToolError("not enough products")):
        result = tools["compare_laptops"].func(product_names=["Only One"])
    assert json.loads(result) == {"error": "not enough products"}


def test_inventory_tool_delegates_to_check_inventory():
    tools = {t.name: t for t in _build_product_tools("headphone")}
    with patch("AGENTS.SALES_CREW_FACTORY.check_inventory", return_value={"in_stock": True}) as mock_fn:
        result = tools["check_headphone_inventory"].func(product_name="SoundMax 200")
    mock_fn.assert_called_once_with("headphone", "SoundMax 200")
    assert json.loads(result) == {"in_stock": True}


def test_price_tool_delegates_to_get_current_price():
    tools = {t.name: t for t in _build_product_tools("phone")}
    with patch("AGENTS.SALES_CREW_FACTORY.get_current_price", return_value={"price": 699}) as mock_fn:
        result = tools["get_phone_price"].func(product_name="iPhone 14")
    mock_fn.assert_called_once_with("phone", "iPhone 14")
    assert json.loads(result) == {"price": 699}


# ---------------------------------------------------------------------------
# _build_company_tools -- task 1.3, "show the local store and company
# website"
# ---------------------------------------------------------------------------
def test_build_company_tools_returns_the_two_brand_tools():
    tools = {t.name for t in _build_company_tools()}
    assert tools == {"get_company_info", "find_nearby_stores"}


def test_company_info_tool_delegates_to_get_company_info():
    tools = {t.name: t for t in _build_company_tools()}
    fake_info = {"name": "Trein", "website": "https://www.trein.example.com"}
    with patch("AGENTS.SALES_CREW_FACTORY.get_company_info", return_value=fake_info) as mock_fn:
        result = tools["get_company_info"].func()
    mock_fn.assert_called_once_with()
    assert json.loads(result) == fake_info


def test_store_locator_tool_delegates_to_list_store_locations():
    tools = {t.name: t for t in _build_company_tools()}
    fake_stores = [{"name": "Trein T Nagar", "city": "Chennai"}]
    with patch("AGENTS.SALES_CREW_FACTORY.list_store_locations", return_value=fake_stores) as mock_fn:
        result = tools["find_nearby_stores"].func(city="Chennai")
    mock_fn.assert_called_once_with("Chennai")
    assert json.loads(result) == fake_stores


# ---------------------------------------------------------------------------
# build_sales_crew -- task 1.2, "utilize the CrewAI task setup at max"
# ---------------------------------------------------------------------------
def test_build_sales_crew_gives_the_product_agent_its_scoped_and_company_tools():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    product_agent = crew.agents[0]
    assert {t.name for t in product_agent.tools} == {
        "search_laptops",
        "compare_laptops",
        "check_laptop_inventory",
        "get_laptop_price",
        "get_company_info",
        "find_nearby_stores",
    }


def test_build_sales_crew_gives_the_sales_agent_company_tools_and_allows_delegation():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    sales_agent = crew.agents[-1]
    assert {t.name for t in sales_agent.tools} == {"get_company_info", "find_nearby_stores"}
    # The sales consultant is the last link in the chain that actually
    # answers the customer -- letting it delegate back to the product
    # expert to double-check something before finalizing is one of the
    # "use the crew better" improvements (task 1.2).
    assert sales_agent.allow_delegation is True


def test_build_sales_crew_caches_the_product_agent():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    product_agent = crew.agents[0]
    assert product_agent.cache is True


def test_build_sales_crew_uses_sequential_process():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    assert crew.process == Process.sequential


def test_build_sales_crew_gives_every_task_a_real_expected_output():
    # Every task used to share the same vague "Short Crispy and punchy"
    # placeholder -- expected_output should now be a real, task-specific
    # description of the actual output shape (task 1.2).
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    seen = set()
    for task in crew.tasks:
        assert task.expected_output
        assert task.expected_output.strip() != "Short Crispy and punchy"
        seen.add(task.expected_output)
    # Four distinct tasks should have four distinct, specific descriptions,
    # not one shared generic string copy-pasted across all of them.
    assert len(seen) == len(crew.tasks) == 4


def test_build_sales_crew_wires_task_dependencies_in_order():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    product_task, psychology_task, story_task, sales_task = crew.tasks
    assert psychology_task.context == [product_task]
    assert story_task.context == [product_task, psychology_task]
    assert sales_task.context == [product_task, psychology_task, story_task]


def test_build_sales_crew_works_for_a_brand_new_multiword_category():
    # No AGENT_FUNCS-style enum to update -- any category the catalog has
    # (including a multi-word one) builds a working crew the same way.
    crew = build_sales_crew(category="Air Conditioner", product_noun="air conditioner")
    product_agent = crew.agents[0]
    assert product_agent.role == "Senior Air Conditioner Product Expert"
    assert {t.name for t in product_agent.tools} >= {
        "search_air_conditioners",
        "compare_air_conditioners",
        "check_air_conditioner_inventory",
        "get_air_conditioner_price",
    }
