"""
Tests for AGENTS/SALES_CREW_FACTORY.py -- specifically the CrewAI tool
adapter (_build_product_tools) that gives the product agent compare/
inventory/price/search tools scoped to one category. Crew/Agent/Task
construction itself is exercised indirectly (building a crew is cheap; it
doesn't call the LLM until .kickoff()).
"""
import json
from unittest.mock import patch

from AGENTS.SALES_CREW_FACTORY import _build_product_tools, build_sales_crew


def test_build_product_tools_returns_four_scoped_tools():
    tools = _build_product_tools("laptop")
    names = {t.name for t in tools}
    assert names == {"search_laptops", "compare_laptops", "check_laptop_inventory", "get_laptop_price"}


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


def test_build_sales_crew_gives_the_product_agent_its_tools():
    crew = build_sales_crew(category="Laptop", product_noun="laptop")
    product_agent = crew.agents[0]
    assert {t.name for t in product_agent.tools} == {
        "search_laptops",
        "compare_laptops",
        "check_laptop_inventory",
        "get_laptop_price",
    }
