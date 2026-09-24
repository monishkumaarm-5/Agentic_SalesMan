"""
Tests for MCP/server.py. Doesn't spin up a real stdio transport/subprocess
-- just verifies the tools are registered under the expected names and that
each one delegates to the matching TOOLS/product_tools.py or
TOOLS/company_tools.py function (the actual filtering/comparison/company
logic is tested directly in tests/test_product_tools.py and
tests/test_company_tools.py).
"""
import asyncio
from unittest.mock import patch

import pytest

from MCP.server import mcp

EXPECTED_TOOLS = {
    "list_categories",
    "get_company_info_tool",
    "list_store_locations_tool",
    "search_products_tool",
    "get_product_details_tool",
    "compare_products_tool",
    "check_inventory_tool",
    "get_current_price_tool",
}


def test_all_eight_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


@pytest.mark.parametrize(
    "tool_name,target,args",
    [
        ("search_products_tool", "MCP.server.search_products", {"category": "laptop"}),
        (
            "get_product_details_tool",
            "MCP.server.get_product_details",
            {"category": "laptop", "product_name": "Lenovo LOQ"},
        ),
        (
            "compare_products_tool",
            "MCP.server.compare_products",
            {"category": "laptop", "product_names": ["A", "B"]},
        ),
        (
            "check_inventory_tool",
            "MCP.server.check_inventory",
            {"category": "laptop", "product_name": "Lenovo LOQ"},
        ),
        (
            "get_current_price_tool",
            "MCP.server.get_current_price",
            {"category": "laptop", "product_name": "Lenovo LOQ"},
        ),
        ("list_categories", "MCP.server.list_categories_tool", {}),
        ("get_company_info_tool", "MCP.server.get_company_info", {}),
        (
            "list_store_locations_tool",
            "MCP.server.list_store_locations",
            {"city": "Chennai"},
        ),
    ],
)
def test_tool_delegates_to_the_matching_underlying_function(tool_name, target, args):
    with patch(target, return_value={"ok": True}) as mock_fn:
        result = asyncio.run(mcp.call_tool(tool_name, args))
    mock_fn.assert_called_once()
    # FastMCP wraps the return value in its content protocol; just confirm
    # the call succeeded and didn't error.
    assert result is not None


def test_list_store_locations_tool_works_with_no_city_filter():
    with patch("MCP.server.list_store_locations", return_value=[]) as mock_fn:
        result = asyncio.run(mcp.call_tool("list_store_locations_tool", {}))
    mock_fn.assert_called_once_with(None)
    assert result is not None
