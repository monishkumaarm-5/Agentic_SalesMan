"""Shared Gemini client construction and a typed structured-output call."""
import logging
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
        "max_retries": 2,
    }
    if s.llm_temperature is not None:
        options["temperature"] = s.llm_temperature
    return ChatGoogleGenerativeAI(**options)


def structured_call(schema: type[T], system: str, user: str, variables: dict) -> T:
    """Runs one prompt and parses the reply into `schema`. Raises on any
    failure -- callers decide their own fallback."""
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", user)])
    chain = prompt | get_chat_model().with_structured_output(schema)
    result = chain.invoke(variables)
    if result is None:
        raise ValueError(f"LLM returned no parsable {schema.__name__}")
    if isinstance(result, dict):
        result = schema.model_validate(result)
    return result
