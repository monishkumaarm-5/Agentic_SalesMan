from typing import Any, Literal

from pydantic import BaseModel, Field

THREAD_ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,128}$"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="The customer's message")
    thread_id: str | None = Field(
        default=None, pattern=THREAD_ID_PATTERN,
        description="Conversation id; a new one is created and returned when omitted",
    )


class StoreInfo(BaseModel):
    name: str
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    hours: str | None = None
    nearby: bool = False
    maps_url: str | None = None


class Spec(BaseModel):
    key: str
    label: str
    value: str


class Match(BaseModel):
    overall: float | None = None
    components: dict[str, float] = {}


class ProductCard(BaseModel):
    rank: int = 1
    id: Any | None = None
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    mrp: float | None = None
    discount_percent: int | None = None
    currency: str = "INR"
    rating: float | None = None
    units_available: int | None = None
    in_stock: bool | None = None
    online_link: str | None = None
    offline_availability: str | None = None
    stores: list[StoreInfo] = []
    description: str | None = None
    specs: list[Spec] = []
    headline: str | None = None
    why: str | None = None
    key_features: list[str] = []
    fit_reasons: list[str] = []
    match: Match = Match()


class RecommendationGroup(BaseModel):
    category: str
    picks: list[ProductCard]


class ChatResponse(BaseModel):
    thread_id: str
    answer: str = Field(description="Markdown reply")
    response_type: Literal["message", "clarification", "recommendation", "comparison"] = "message"
    recommendations: list[RecommendationGroup] = Field(
        default_factory=list, description="Product picks, grouped by category")
    products: list[ProductCard] = Field(default_factory=list, description="Products the answer is about")
    comparison: list[ProductCard] = Field(default_factory=list, description="Products to show side by side")
    suggestions: list[str] = Field(default_factory=list, description="Quick replies for the customer")
    profile: dict = Field(default_factory=dict, description="What the assistant knows about the customer's needs")
    confidence: float | None = Field(default=None, description="Best pick's 0-1 fit score")


class HistoryTurn(BaseModel):
    role: str
    content: str


class CategorySummary(BaseModel):
    name: str
    product_count: int
    min_price: float | None = None
    max_price: float | None = None
    brands: list[str] = []


class CompareRequest(BaseModel):
    product_names: list[str] = Field(..., min_length=2, max_length=6)
    category: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict
