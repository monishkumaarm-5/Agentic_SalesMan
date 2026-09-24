"""Conversational shopping agent used by WORKFLOW.ORCHE."""

from __future__ import annotations

import os
from typing import Optional

import config
from langchain_google_genai import ChatGoogleGenerativeAI


def _system_prompt() -> str:
    """Built at call time (not a module-level constant) so a COMPANY_NAME
    change in config.py takes effect without restarting anything beyond a
    normal process reload -- there's no caching to invalidate."""
    company_name = getattr(config, "COMPANY_NAME", "Trein")
    return f"""
You are the conversational assistant for {company_name}, a multi-category
retail shopping application.

You can discuss anything {company_name} sells -- mobiles, laptops,
headphones, TVs, home appliances and more.

Your job in CHAT mode is to behave like a normal conversational assistant:
- Answer questions naturally and clearly.
- Use the supplied conversation history to resolve references and follow-up questions.
- Do not invent product specifications, prices, availability, links, or purchase information.
- Do not produce a product recommendation unless the user explicitly asks for one or clearly wants help selecting a product.
- When the user is only chatting, explaining something, greeting, or asking a general question, respond conversationally.
- When the user asks for a recommendation, let the recommendation workflow handle product retrieval rather than inventing products here.
""".strip()


def _api_key() -> str:
    key = getattr(config, "GOOGLE_API_KEY", None) or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    return key


def _model() -> ChatGoogleGenerativeAI:
    model_name = getattr(config, "CHATBOT_MODEL", None) or getattr(
        config, "GEMINI_MODEL", None
    ) or "gemini-3.1-flash-lite"

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=_api_key(),
        temperature=getattr(config, "CHATBOT_TEMPERATURE", 0.3),
    )


def _extract_text(response) -> str:
    content = getattr(response, "content", response)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()

    return str(content).strip()


def CHATBOT_AGENT(prompt: str, history: Optional[list] = None) -> str:
    """
    Generate a conversational response.

    `history` is optional because ORCHE.py already gets it from the LangGraph
    checkpoint state and embeds it into `prompt`. It is accepted explicitly so
    the agent can also be reused directly when needed.
    """
    history_text = ""

    if history:
        history_text = "\n".join(
            f"{turn.get('role', 'unknown')}: {turn.get('content', '')}"
            for turn in history[-6:]
        )

    if history_text and "Previous conversation:" not in prompt:
        prompt = f"Previous conversation:\n{history_text}\n\nCurrent request:\n{prompt}"

    messages = [
        ("system", _system_prompt()),
        ("human", prompt),
    ]

    response = _model().invoke(messages)
    return _extract_text(response)


__all__ = ["CHATBOT_AGENT"]
