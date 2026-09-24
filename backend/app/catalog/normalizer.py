"""
Best-effort LLM fill for product attributes that most of a category's
products have but this one is missing (see app.catalog.schema). Never
raises and never overwrites an existing value.
"""
import logging

from pydantic import create_model

from app.agents.llm import structured_call

logger = logging.getLogger("salesman.catalog.normalizer")

SYSTEM = (
    "You extract product specifications for a retail catalog. Only extract a "
    "fact that is stated or very strongly implied by the product name or "
    "description. Leave a field null when unsure -- never guess."
)

USER = (
    "Category: {category}\nProduct name: {name}\nDescription: {description}\n"
    "Existing specs: {existing}\n\nFill these fields using short values in the "
    "same style as the existing specs (e.g. \"8GB\", \"5000mAh\"): {fields}"
)


def fill_missing_attributes(category: str, name: str, description: str,
                            attributes: dict, missing: set[str]) -> dict:
    if not missing:
        return attributes
    fields = sorted(missing)
    model = create_model("ExtractedSpecs", **{f: (str | None, None) for f in fields})
    try:
        result = structured_call(model, SYSTEM, USER, {
            "category": category,
            "name": name or "",
            "description": description or "",
            "existing": attributes or {},
            "fields": ", ".join(fields),
        })
    except Exception as exc:  # noqa: BLE001
        logger.info("Attribute fill skipped for %r: %s", name, exc)
        return attributes

    extracted = {
        key: value for key, value in result.model_dump().items()
        if value not in (None, "") and key not in attributes
    }
    if extracted:
        logger.info("Filled %s for %r", sorted(extracted), name)
    return {**attributes, **extracted}
