"""Conversation state persisted per thread by the LangGraph checkpointer."""
from typing import Annotated, TypedDict


def append(base: list | None, update: list | None) -> list:
    return list(base or []) + list(update or [])


def merge_turn(base: dict | None, update: dict | None) -> dict:
    """Per-turn scratch space. An update carrying `_reset` starts a fresh
    turn; any other update is merged in."""
    update = dict(update or {})
    if update.pop("_reset", False):
        return update
    return {**(base or {}), **update}


class ChatState(TypedDict, total=False):
    # The customer's message for the current turn.
    message: str
    # Full transcript: [{"role": "user"|"assistant", "content": str}].
    messages: Annotated[list, append]
    # ShoppingProfile as a dict -- what we know about what they want.
    profile: dict
    # category -> product cards most recently shown for it.
    shown: dict
    # Consecutive clarifying questions asked (reset by any other action).
    clarify_streak: int
    # This turn's working data and final response (see nodes.finalize).
    turn: Annotated[dict, merge_turn]
