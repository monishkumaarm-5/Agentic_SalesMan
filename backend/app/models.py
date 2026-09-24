"""Domain models shared by the agents, workflow and API."""

from pydantic import BaseModel, Field, field_validator


class ShoppingProfile(BaseModel):
    """Everything learned about what the customer wants. Rebuilt by the
    understanding agent on every turn, so it can grow, change or be
    cleared as the conversation moves on."""

    categories: list[str] = Field(default_factory=list, description="Catalog categories being shopped for")
    budget_min: float | None = Field(default=None, description="Lowest price they'd consider")
    budget_max: float | None = Field(default=None, description="Highest price they'd pay")
    use_cases: list[str] = Field(default_factory=list, description="What it will be used for, e.g. 'gaming'")
    must_haves: list[str] = Field(default_factory=list, description="Concrete features they asked for, e.g. '5G', '16GB RAM'")
    preferred_brands: list[str] = Field(default_factory=list)
    avoid_brands: list[str] = Field(default_factory=list)
    city: str | None = Field(default=None, description="Customer's city, for store availability")
    motivation: str | None = Field(default=None, description="Why they're buying, in a few words")

    @field_validator("categories", "use_cases", "must_haves", "preferred_brands", "avoid_brands", mode="before")
    @classmethod
    def _clean_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        seen, out = set(), []
        for item in value:
            text = str(item).strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                out.append(text)
        return out

    @field_validator("budget_min", "budget_max", mode="before")
    @classmethod
    def _positive(cls, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def is_empty(self) -> bool:
        return not any(self.model_dump(exclude_none=True, exclude_defaults=True).values())
