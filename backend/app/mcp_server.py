"""
MCP (Model Context Protocol) server exposing the store catalog as tools
for any MCP client (Claude Desktop, Claude Code, other agents).

    python -m app.mcp_server        # stdio transport, run from backend/
"""
import logging

from mcp.server.fastmcp import FastMCP

from app import company
from app.catalog import database, tools

mcp = FastMCP(
    name="agentic-salesman",
    instructions=(
        "Tools for this store's product catalog and showrooms. The catalog is "
        "data-driven: call list_categories first instead of assuming categories."
    ),
)


@mcp.tool()
def list_categories() -> list:
    """Every product category with product count, price range and brands."""
    return database.category_overview()


@mcp.tool()
def store_info(city: str | None = None) -> dict:
    """The store's name, website, support phone and showrooms (optionally in one city)."""
    return {**company.company_info(), "stores": company.list_stores(city)}


@mcp.tool()
def search_products(category: str | None = None, min_price: float | None = None,
                    max_price: float | None = None, brand: str | None = None,
                    keyword: str | None = None, limit: int = 10) -> list:
    """Search products with optional filters; keyword matches any text field."""
    return tools.search_products(category, min_price, max_price, brand, keyword, limit)


@mcp.tool()
def product_details(product_name: str) -> dict | None:
    """Full details for one product (name is fuzzy-matched)."""
    return tools.get_product_details(product_name)


@mcp.tool()
def compare_products(product_names: list[str]) -> dict:
    """Side-by-side data for 2-6 products plus the fields that differ."""
    return tools.compare_products(product_names)


@mcp.tool()
def check_stock(product_name: str) -> dict:
    """Units in stock and showroom availability for a product."""
    return tools.check_inventory(product_name)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
