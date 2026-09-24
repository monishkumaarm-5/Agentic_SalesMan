"""
LLM-based normalization for catalog rows that are missing required
attributes at ingestion time.

Same pattern as AGENTS/REQUIREMENT_EXTRACTOR_AGENT.py's structured-output
Gemini call, just applied to a product row instead of a chat turn: a
small, single-purpose LLM call that fails open. A failed or malformed
extraction leaves the row's attributes untouched, and the ingestion gate
(TOOLS/product_schema.missing_fields) simply marks the product incomplete
rather than storing partial data -- this module never blocks a sync, it
only sometimes helps a row pass the gate that would otherwise fail it.

Only called for rows that already failed TOOLS.product_schema.
missing_fields(), and only for the category-specific fields (never for
name/brand/price -- there is nothing to reliably infer those from, they
should already identify the product).
"""
import logging
from typing import Optional

from langchain_core.prompts import PromptTemplate
from AGENTS.llm import build_llm
from pydantic import create_model

logger = logging.getLogger("agentic_salesman.product_normalizer")

prompt_template = PromptTemplate.from_template(
    """
    Role: Catalog data assistant. A product listing is missing some of
    the structured specifications a shopping assistant needs to search
    and compare it. Extract them from the product's name and
    description alone.

    Only extract a fact that is actually stated or very strongly implied
    by the name/description -- leave a field null if you are not
    confident, rather than guessing.

    Product category: {category}
    Product name: {name}
    Product description: {description}

    Fields to extract: {fields}

    Output ONLY JSON with exactly these keys, using a short plain-text
    value for each (matching how this catalog already writes specs, e.g.
    "8GB", "5000mAh", "15.6-inch FHD"), or null when not confidently
    determinable.
    """
)

llm = build_llm()


def _model_for_fields(fields):
    """A throwaway Pydantic model with one Optional[str] field per
    missing attribute. Built at call time rather than declared as a
    fixed class (contrast REQUIREMENT_EXTRACTOR_AGENT.py's Requirements
    model) because the field set varies by category and is only known
    once TOOLS.product_schema.missing_fields has already run."""
    return create_model(
        "NormalizedSpecs",
        **{field: (Optional[str], None) for field in fields},
    )


def _call_llm(category: str, name: str, description: str, fields):
    """Isolated so tests can monkeypatch just the LLM call, the same way
    tests/test_requirement_extractor.py does for _call_llm there."""
    model = _model_for_fields(fields)
    structured_llm = llm.with_structured_output(model)
    chain = prompt_template | structured_llm
    return chain.invoke(
        {
            "category": category,
            "name": name or "",
            "description": description or "",
            "fields": ", ".join(fields),
        }
    )


def normalize_with_llm(
    category: str,
    name: str,
    description: str,
    attributes: dict,
    missing: set,
) -> dict:
    """Best-effort fill of the `missing` attribute keys from the
    product's name/description. Returns a NEW attributes dict (the
    existing attributes plus whatever the LLM confidently extracted);
    never raises, never removes or overwrites an attribute that was
    already present."""
    if not missing:
        return attributes

    fields = sorted(missing)

    try:
        result = _call_llm(category, name, description, fields)
        extracted = {
            key: value
            for key, value in result.model_dump().items()
            if value not in (None, "") and key not in attributes
        }
    except Exception as exc:
        logger.warning(
            "Product normalization failed for %r (%s); leaving attributes as-is",
            name, exc,
        )
        return attributes

    if extracted:
        logger.info("LLM-normalized %r for %r: %s", list(extracted), name, category)

    return {**attributes, **extracted}


__all__ = ["normalize_with_llm"]
