"""Shared Gemini client construction and a typed structured-output call."""
import logging
import time
from functools import lru_cache
from typing import TypeVar

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("salesman.llm")

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Raised when no API key is configured."""


@lru_cache(maxsize=1)
def get_chat_model():
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    if not s.llm_configured:
        raise LLMUnavailable("GOOGLE_API_KEY is not configured")
    options = {
        "model": s.llm_model,
        "google_api_key": s.google_api_key,
        "timeout": s.llm_timeout_seconds,
        "max_retries": s.llm_max_retries,
    }
    if s.llm_temperature is not None:
        options["temperature"] = s.llm_temperature
    return ChatGoogleGenerativeAI(**options)


# Which agent each output schema belongs to, for logs.
AGENT_NAMES = {
    "Understanding": "UnderstandingAgent",
    "RecommendationOutput": "RecommenderAgent",
    "AdvisorOutput": "AdvisorAgent",
    "ExtractedSpecs": "CatalogNormalizer",
}


def agent_name(schema: type[BaseModel]) -> str:
    return AGENT_NAMES.get(schema.__name__, schema.__name__)


def _preview(text: str, limit: int = 800) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} chars)"


def structured_call(schema: type[T], system: str, user: str, variables: dict) -> T:
    """Runs one prompt and parses the reply into `schema`. Raises on any
    failure -- callers decide their own fallback. Every call is logged
    with the agent, model, prompt size, latency and parsed output."""
    settings = get_settings()
    agent = agent_name(schema)
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", user)])
    messages = prompt.format_messages(**variables)
    prompt_chars = sum(len(str(m.content)) for m in messages)

    logger.info("LLM ▶ %s | model=%s | prompt=%d chars", agent, settings.llm_model, prompt_chars)
    if settings.log_llm_prompts:
        for m in messages:
            logger.info("LLM   %s prompt [%s]:\n%s", agent, m.type, m.content)

    started = time.monotonic()
    try:
        result = get_chat_model().with_structured_output(schema).invoke(messages)
        if result is None:
            raise ValueError(f"LLM returned no parsable {schema.__name__}")
        if isinstance(result, dict):
            result = schema.model_validate(result)
    except Exception as exc:
        logger.warning("LLM ✗ %s failed after %dms: %s: %s", agent,
                       (time.monotonic() - started) * 1000, type(exc).__name__, exc)
        raise

    output = result.model_dump_json()
    logger.info("LLM ✓ %s | %dms | output: %s", agent, (time.monotonic() - started) * 1000,
                output if settings.log_llm_prompts else _preview(output))
    return result
