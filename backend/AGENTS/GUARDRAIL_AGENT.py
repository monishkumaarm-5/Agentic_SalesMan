"""
Guardrail Agent -- predefined-rules replacement for the old LLM-backed
entry guard (ENTRYSAFEGAURD_AGENT.isvalidquery) and exit evaluator
(EXIT_SAFE_GAURD_AGENT.evaluate_response). Run twice per turn: once on the
way in (entry_check), once on the way out (exit_check).

Why: the old entry/exit guards spent a full Gemini call on every single
turn just to reject spam, injection attempts, and empty messages, and to
grade answers that were often already trivially fine. Rules catch the
cheap, high-confidence cases for free -- no LLM round trip, no token cost,
no latency -- and leave real judgment calls (is this actually a sensible
shopping request? does this answer actually satisfy the customer?) to the
LLM-backed agents downstream, which were going to be called anyway.

This is deliberately NOT a semantic classifier. It will not catch a
subtly off-topic message or a subtly wrong factual claim. Business Need
Agent (AGENTS/BUSINESS_NEED_AGENT.py) is expected to redirect a message
that isn't really a shopping request once it gets there; Product Expert /
Sales Consultant are only ever allowed to talk about products already
present in `candidates`, which is what keeps their answers grounded --
this module's exit_check is a last, cheap safety net on top of that, not
the only thing standing between the customer and a hallucination.
"""
import re
from typing import List, Optional

# Phrases aimed at Claude/Gemini itself rather than at the shopping
# assistant's actual job -- classic prompt-injection / jailbreak framing.
# Kept as a short, readable list (not an exhaustive security boundary) so
# it's easy to see exactly what this blocks and extend it later.
_INJECTION_PATTERNS = [
    r"ignore (all |any |previous |prior |the )*instructions",
    r"disregard (the|your|all|any) (rules|guidelines|instructions)",
    r"system prompt",
    r"reveal your (prompt|instructions|rules|system)",
    r"you are now (a|an)? ?(?!.{0,3}(shopping|sales))",
    r"act as (a|an) (?!.{0,20}(shopping|sales|customer))",
    r"pretend (you|to) (are|be)",
    r"jailbreak",
    r"\bdan mode\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Small-talk openers/closers that carry no shopping content on their own.
# Matched as a whole-message prefix (after trimming punctuation), not a
# substring, so "hi, do you have any laptops under 50000" is correctly
# left for Business Need Agent to handle as a real request.
_GREETING_PHRASES = (
    "hi", "hii", "hiii", "hello", "hey", "yo", "hiya", "greetings",
    "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "thx", "ty", "thanks a lot", "thank you so much",
    "bye", "goodbye", "see you", "cya", "take care",
    "how are you", "how are you doing", "what's up", "whats up", "sup",
)

# A message this long is either an accident (paste, spam) or trying to
# bury an injection attempt in noise -- reject cheaply rather than pass
# it to an LLM call that will burn a lot of input tokens either way.
_MAX_MESSAGE_CHARS = 2000

_PLACEHOLDER_ANSWER_MARKERS = ("todo", "lorem ipsum", "fixme", "n/a - ")


# Words that can trail a greeting without adding any shopping content
# ("hi there", "hello team", "thanks a lot bot").
_GREETING_FILLER = {"there", "team", "bot", "assistant", "all", "everyone", "friend", "again", "so", "much", "a", "lot"}

_GREETING_RE = re.compile(
    r"^(?:" + "|".join(sorted((re.escape(p) for p in _GREETING_PHRASES), key=len, reverse=True)) + r")\b"
)


def _looks_like_greeting(text: str) -> bool:
    """True only for pure small talk. A message that merely *starts* with a
    greeting ("hey, can you recommend a laptop under 50000?") is a real
    shopping request and must not be answered with the canned greeting."""
    normalized = re.sub(r"[^\w\s']", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return False

    # Peel greeting phrases off the front repeatedly ("hi, good morning!").
    while True:
        match = _GREETING_RE.match(normalized)
        if not match:
            break
        normalized = normalized[match.end():].strip()

    if normalized == text.lower().strip():
        return False  # didn't start with a greeting at all
    leftover = [word for word in normalized.split() if word not in _GREETING_FILLER]
    return not leftover


# Common everyday words for a catalog category that don't literally
# contain the category's own catalog name -- a small, honest patch over
# pure substring matching, not real language understanding. This list is
# a hint-quality mitigation, not a completeness guarantee: an alias this
# table doesn't know about just means guardrail_in falls back to treating
# the message as a follow-up on whatever category is already active,
# which Business Need Agent / Sales Consultant Agent can still correct
# from their own (LLM-backed) reading of the message -- see ORCHE.py's
# module docstring for how that self-correction path works.
_CATEGORY_ALIASES = {
    "mobile": ("phone", "smartphone", "iphone", "android", "cellphone", "cell phone", "mobile phone"),
    "laptop": ("notebook", "macbook", "ultrabook", "chromebook"),
    "tablet": ("ipad", "tab"),
    "headphone": ("earphone", "earbud", "headset", "airpods", "tws"),
    "speaker": ("soundbar", "bluetooth speaker"),
    "smartwatch": ("smart watch", "fitness band", "fitness tracker", "apple watch"),
    "refrigerator": ("fridge",),
    "television": ("tv", "smart tv", "led tv", "oled"),
    "air conditioner": ("ac", "aircon", "split ac", "window ac"),
    "washing machine": ("washer",),
    "microwave oven": ("microwave", "otg"),
    "mixer grinder": ("mixer", "grinder", "mixie", "blender"),
}


def _term_pattern(term: str) -> re.Pattern:
    """Whole-word match for a category name or alias, tolerating a plural
    ("laptops", "watches") -- plain substring matching mis-fired on
    "headphones" (contains "phone" -> Mobile), "black"/"each" (contain
    "ac" -> Air Conditioner) and "dishwasher" (contains "washer")."""
    words = [re.escape(word) for word in term.lower().split()]
    return re.compile(r"\b" + r"\s+".join(words) + r"(?:s|es)?\b")


def _matched_categories(text: str, known_categories: List[str]) -> List[str]:
    """Cheap substring match against the live catalog, plus a small known
    -alias table -- not classification, just "does the category's own
    name (or a common everyday word for it) appear in the message". This
    is only ever used as a *hint* for guardrail_in's routing; Business
    Need Agent still does the real (LLM-backed) multi-category
    understanding on top of it."""
    lowered = text.lower()
    matched = []
    for cat in known_categories:
        cat_lower = str(cat).strip().lower()
        if not cat_lower:
            continue
        terms = (cat_lower,) + _CATEGORY_ALIASES.get(cat_lower, ())
        if any(_term_pattern(term).search(lowered) for term in terms):
            matched.append(cat)
    return matched


def detect_categories(text: str, known_categories: Optional[List[str]] = None) -> List[str]:
    """Public wrapper around the same cheap substring/alias match
    `entry_check` uses internally -- for callers that need a fresh,
    standalone category check on a single message without running the
    full entry_check (e.g. Business Need Agent corroborating an LLM's
    proposed category switch away from one already established this
    conversation, before trusting it -- see ORCHE.py's business_need_agent
    node)."""
    return _matched_categories(text or "", known_categories or [])


def entry_check(question: str, known_categories: Optional[List[str]] = None) -> dict:
    """Rule-based first pass on an incoming message. Never calls an LLM.

    Returns:
      is_valid        -- False only for injection attempts / empty /
                          absurdly long input. Deliberately conservative
                          about rejecting -- anything let through here
                          still has to make sense to Business Need Agent
                          right after it, so this only needs to catch the
                          cheap, unambiguous cases.
      is_greeting      -- pure small talk, no shopping content at all.
      category_hints   -- catalog categories whose own name literally
                           appears in the message (a hint, not a verdict).
      reason           -- short machine-readable reason, for logging.
    """
    known_categories = known_categories or []
    text = (question or "").strip()

    if not text:
        return {"is_valid": False, "is_greeting": False, "category_hints": [], "reason": "empty_message"}

    if len(text) > _MAX_MESSAGE_CHARS:
        return {"is_valid": False, "is_greeting": False, "category_hints": [], "reason": "message_too_long"}

    if _INJECTION_RE.search(text):
        return {"is_valid": False, "is_greeting": False, "category_hints": [], "reason": "injection_pattern"}

    return {
        "is_valid": True,
        "is_greeting": _looks_like_greeting(text),
        "category_hints": _matched_categories(text, known_categories),
        "reason": "ok",
    }


def exit_check(answer: str, candidates: Optional[dict] = None) -> dict:
    """Rule-based last pass on an outgoing answer, before it reaches the
    customer. Never calls an LLM.

    This does not (and, without an LLM, cannot) verify every factual claim
    in the answer -- it catches the free, high-confidence failure modes:
    an empty or placeholder answer, or a raw JSON/traceback leak. Product
    Expert Agent and Sales Consultant Agent are only ever allowed to work
    from `candidates` already fetched from the catalog, which is what
    keeps ordinary answers grounded; this is the cheap safety net on top
    of that, not a replacement for it. `candidates` is accepted for
    forward compatibility but deliberately not used for a "mentions a
    known name" check -- see the note inline below for why.

    Returns {"passed": bool, "reason": str}.
    """
    text = (answer or "").strip()

    if not text:
        return {"passed": False, "reason": "empty_answer"}

    lowered = text.lower()

    if lowered.startswith("{") or lowered.startswith("["):
        return {"passed": False, "reason": "raw_structured_output_leak"}

    if "traceback (most recent call last)" in lowered:
        return {"passed": False, "reason": "traceback_leak"}

    if len(text) < 40 and any(marker in lowered for marker in _PLACEHOLDER_ANSWER_MARKERS):
        return {"passed": False, "reason": "placeholder_answer"}

    # Deliberately NOT checking "does the answer mention a known product
    # name" here, even though `candidates` is accepted for that purpose --
    # a short, perfectly good follow-up reply ("yes, it has great battery
    # life") often doesn't restate the product's name, and a rule that
    # can't tell that apart from a hallucinated name would silently
    # replace good answers with a decline far more often than it would
    # ever catch a real hallucination. Product Expert / Sales Consultant
    # Agent are the actual groundedness mechanism (both are only ever
    # given the retrieved `candidates` to work from); this stays limited
    # to the format-level failure modes above, which have no false-
    # positive cost.
    return {"passed": True, "reason": "ok"}


__all__ = ["entry_check", "exit_check", "detect_categories"]
