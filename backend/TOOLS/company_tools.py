"""
Company/store lookup tools -- the "who are we and where can you find us"
counterpart to TOOLS/product_tools.py's catalog tools.

This is what task 1.3 (this is a company-specific app -- the local store
and the company website need to actually show up) is built on: without
this, nothing in the pipeline knew this was "Trein" rather than a generic
assistant, or that Trein has physical stores at all. Kept as plain,
framework-agnostic functions (same reasoning as product_tools.py's
docstring) so they can be handed to CrewAI agents as tools (see
AGENTS/SALES_CREW_FACTORY.py's _build_company_tools), exposed over the API
(ENDPOINTS/endpoints.py's GET /api/company), and unit tested with no LLM
or MCP transport involved.

All of it reads from config.py's COMPANY_NAME/COMPANY_WEBSITE/
STORE_LOCATIONS -- see that module for the (placeholder, edit-before-
production) values.
"""
from typing import Optional

import config


def get_company_info() -> dict:
    """Brand-level facts an agent or the API can hand back verbatim --
    never invented, always read straight from config.py so a rebrand is a
    one-file edit, not a find-and-replace across prompts."""
    stores = getattr(config, "STORE_LOCATIONS", None) or []
    return {
        "name": getattr(config, "COMPANY_NAME", "Trein"),
        "tagline": getattr(config, "COMPANY_TAGLINE", ""),
        "website": getattr(config, "COMPANY_WEBSITE", ""),
        "support_phone": getattr(config, "COMPANY_SUPPORT_PHONE", ""),
        "store_count": len(stores),
    }


def list_store_locations(city: Optional[str] = None) -> list:
    """All configured showrooms, or just the ones in `city` (case-
    insensitive substring match, e.g. "chennai" matches "Chennai"). Returns
    [] rather than raising for a city with no stores -- "we don't have a
    store there" is a normal, expected answer, not an error."""
    stores = getattr(config, "STORE_LOCATIONS", None) or []
    if not city or not city.strip():
        return list(stores)

    needle = city.strip().lower()
    return [store for store in stores if needle in str(store.get("city", "")).lower()]


__all__ = ["get_company_info", "list_store_locations"]
