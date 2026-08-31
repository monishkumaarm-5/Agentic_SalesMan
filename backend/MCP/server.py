"""
Standalone MCP server exposing the Agentic SalesMan product catalog as
tools any MCP client can call -- Claude Desktop, Claude Code, another
agent, or a debugging session with the MCP inspector.

This does NOT sit in the hot path of a chat request: the CrewAI product
agent calls TOOLS/product_tools.py directly, in-process, for latency (see
AGENTS/SALES_CREW_FACTORY.py). This server registers the *same* functions
as MCP tools on top, so the catalog is reachable over the protocol too,
without maintaining two implementations.

Run it directly:
    python -m MCP.server

Then point an MCP client at it over stdio. For Claude Desktop/Code, add
something like this to its MCP config:
    {
      "mcpServers": {
        "agentic-salesman": {
          "command": "python",
          "args": ["-m", "MCP.server"],
          "cwd": "/path/to/Agentic_SalesMan"
        }
      }
    }
"""
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from TOOLS.product_tools import (
    check_inventory,
    compare_products,
    get_current_price,
    get_product_details,
    search_products,
)

logger = logging.getLogger("agentic_salesman.mcp")

mcp = FastMCP(
    name="agentic-salesman",
    instructions=(
        "Tools for the Agentic SalesMan product catalog (phones, laptops, "
        "headphones). Categories are 'phone', 'laptop' or 'headphone'. "
        "Products are addressed by name -- there is no product id."
    ),
)


@mcp.tool()
def search_products_tool(
    category: str,
    max_price: Optional[float] = None,
    min_ram_gb: Optional[float] = None,
    min_storage_gb: Optional[float] = None,
    brand: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 10,
) -> list:
    """Search the product catalog with structured filters. category must be
    one of 'phone', 'laptop', 'headphone'. All filters are optional."""
    return search_products(
        category,
        max_price=max_price,
        min_ram_gb=min_ram_gb,
        min_storage_gb=min_storage_gb,
        brand=brand,
        keyword=keyword,
        limit=limit,
    )


@mcp.tool()
def get_product_details_tool(category: str, product_name: str) -> Optional[dict]:
    """Look up full details for one product by name (fuzzy-matched).
    Returns null if nothing matches closely enough."""
    return get_product_details(category, product_name)


@mcp.tool()
def compare_products_tool(category: str, product_names: list) -> dict:
    """Compare 2+ products in the same category side by side. Returns each
    product's full data plus the list of fields that differ between them."""
    return compare_products(category, product_names)


@mcp.tool()
def check_inventory_tool(category: str, product_name: str) -> dict:
    """Check whether a product is in stock. Note: the sample catalog has no
    dedicated inventory table, so this reports catalog presence unless a
    real stock/quantity column exists -- see the returned "source" field."""
    return check_inventory(category, product_name)


@mcp.tool()
def get_current_price_tool(category: str, product_name: str) -> dict:
    """Get the current price of a product by name."""
    return get_current_price(category, product_name)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Agentic SalesMan MCP server (stdio transport)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
