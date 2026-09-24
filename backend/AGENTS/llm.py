"""
Single place that builds the Gemini chat model every agent uses, so the
model name and API key come from config.py (or the LLM_MODEL /
GOOGLE_API_KEY env vars) instead of being hard-coded per module.
"""
from langchain_google_genai import ChatGoogleGenerativeAI

import config

DEFAULT_LLM_MODEL = "gemini-3.1-flash-lite"


def build_llm(**kwargs) -> ChatGoogleGenerativeAI:
    options = {
        "model": getattr(config, "LLM_MODEL", None) or DEFAULT_LLM_MODEL,
        "temperature": getattr(config, "LLM_TEMPERATURE", None),
    }
    api_key = getattr(config, "GOOGLE_API_KEY", None)
    if api_key and api_key != "your-google-api-key-here":
        options["google_api_key"] = api_key
    options.update(kwargs)
    return ChatGoogleGenerativeAI(**{k: v for k, v in options.items() if v is not None})


__all__ = ["build_llm", "DEFAULT_LLM_MODEL"]
