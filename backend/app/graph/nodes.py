"""
Workflow nodes. Each turn:

    guard ─▶ understand ─┬─▶ finalize                       (reply / clarify)
                         ├─▶ retrieve ─▶ recommend ─▶ finalize (recommend / alternatives)
                         └─▶ advise ─▶ finalize             (discuss)

`understand` (an LLM) decides the route from the conversation itself.
The code around it only enforces a few invariants the model can't be
trusted with -- e.g. you can't recommend without knowing what kind of
product, and you can't discuss products nobody has named or seen.
"""
import logging
import time

from langgraph.config import get_stream_writer

from app.agents import context as ctx
from app.agents.understanding import Understanding
from app.catalog.utils import format_price
from app.core.config import Settings
from app.graph.state import ChatState
from app.graph.toolkit import Toolkit
from app.models import ShoppingProfile
from app.retrieval.cards import build_card, match_name
from app.retrieval.search import budget_note, hybrid_search

logger = logging.getLogger("salesman.graph")

MAX_MESSAGE_CHARS = 2000

STEP_LABELS = {
    "understand": "Understanding what you need",
    "retrieve": "Searching the catalog",
    "recommend": "Picking the best matches for you",
    "advise": "Checking the product details",
}


def _status(step: str, label: str | None = None) -> None:
    try:
        get_stream_writer()({"type": "status", "step": step, "label": label or STEP_LABELS.get(step, step)})
    except Exception:  # noqa: BLE001 - not running under stream()
        pass


def _profile(state: ChatState) -> ShoppingProfile:
    try:
        return ShoppingProfile.model_validate(state.get("profile") or {})
    except Exception:  # noqa: BLE001
        return ShoppingProfile()


def _shown_names(shown: dict, category: str | None = None) -> list[str]:
    cards = shown.get(category, []) if category else [c for cs in shown.values() for c in cs or []]
    return [c.get("name") for c in cards if c.get("name")]


def _suggestions(items, limit: int = 4) -> list[str]:
    seen, out = set(), []
    for item in items or []:
        text = " ".join(str(item).split())[:60]
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out[:limit]


class Nodes:
    def __init__(self, toolkit: Toolkit, settings: Settings):
        self.tk = toolkit
        self.s = settings

    # ------------------------------------------------------------------ guard
    def guard(self, state: ChatState) -> dict:
        message = " ".join(str(state.get("message") or "").split())
        turn = {"_reset": True, "started_at": time.time(), "steps": []}
        if not message:
            turn.update(action="reply", answer="It looks like that message was empty -- what can I help you find?")
        elif len(message) > MAX_MESSAGE_CHARS:
            turn.update(action="reply", answer=(
                "That message is a bit long for me. Could you tell me in a sentence or two "
                "what you're looking for?"))
        return {"message": message, "turn": turn}

    @staticmethod
    def route_after_guard(state: ChatState) -> str:
        return "finalize" if (state.get("turn") or {}).get("action") else "understand"

    # ------------------------------------------------------------- understand
    def understand(self, state: ChatState) -> dict:
        _status("understand")
        started = time.monotonic()
        overview = self.tk.catalog_overview() or []
        known = {c["name"].lower(): c["name"] for c in overview}
        profile = _profile(state)
        shown = state.get("shown") or {}
        streak = int(state.get("clarify_streak") or 0)

        try:
            result: Understanding = self.tk.understand({
                "company": self.s.company_name,
                "currency": self.s.company_currency,
                "store": ctx.store_context(),
                "catalog": ctx.catalog_context(overview),
                "profile": ctx.profile_context(profile),
                "shown": ctx.shown_context(shown),
                "clarify_streak": streak,
                "max_clarify": self.s.max_clarifying_questions,
                "history": ctx.history_context(state.get("messages") or [], self.s.history_window),
                "message": state.get("message", ""),
            })
            new_profile = result.profile
            action, reply = result.action, result.reply.strip()
            referenced, suggestions = result.referenced_products, result.suggestions
            degraded = False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Understanding failed (%s); continuing with what we know", exc)
            new_profile, referenced, degraded = profile, [], True
            action = "recommend" if profile.categories else "clarify"
            reply, suggestions = "", []

        # Categories must exist in the live catalog (if we could load it).
        if known:
            new_profile.categories = [known[c.lower()] for c in new_profile.categories if c.lower() in known]

        action, reply, reason = self._enforce(action, reply, new_profile, shown, referenced, streak, overview)
        if not suggestions and action == "clarify" and not new_profile.categories:
            suggestions = [f"Show me {c['name'].lower()}s" for c in overview[:4]]

        return {
            "profile": new_profile.model_dump(),
            "clarify_streak": streak + 1 if action == "clarify" else 0,
            "turn": {
                "action": action,
                "answer": reply,
                "referenced": referenced,
                "suggestions": _suggestions(suggestions),
                "degraded": degraded,
                "policy": reason,
                "steps": [{"step": "understand", "ms": round((time.monotonic() - started) * 1000)}],
            },
        }

    def _enforce(self, action, reply, profile, shown, referenced, streak, overview):
        """Invariants on top of the model's decision. Returns (action,
        reply, reason) where reason explains any override (for tracing)."""
        if action == "discuss" and not shown and not referenced:
            action = "recommend"
            reason = "discuss_without_products"
        else:
            reason = None
        if action == "clarify" and profile.categories and streak >= self.s.max_clarifying_questions:
            return "recommend", "", "clarify_limit_reached"
        if action in ("recommend", "alternatives") and not profile.categories:
            if not reply:
                names = ", ".join(c["name"].lower() for c in overview[:6])
                reply = ("Happy to help! What are you shopping for today"
                         + (f" -- for example {names}?" if names else "?"))
            return "clarify", reply, reason or "no_category"
        if action in ("reply", "clarify") and not reply:
            reply = ("Could you tell me a little more about what you're looking for -- "
                     "the type of product, and roughly your budget?")
            return "clarify", reply, reason or "empty_reply"
        return action, reply, reason

    @staticmethod
    def route_after_understand(state: ChatState) -> str:
        action = (state.get("turn") or {}).get("action")
        if action in ("recommend", "alternatives"):
            return "retrieve"
        if action == "discuss":
            return "advise"
        return "finalize"

    # --------------------------------------------------------------- retrieve
    def retrieve(self, state: ChatState) -> dict:
        profile = _profile(state)
        turn = state.get("turn") or {}
        shown = state.get("shown") or {}
        started = time.monotonic()
        _status("retrieve", f"Searching {', '.join(c.lower() for c in profile.categories)}")

        candidates, notes = {}, []
        for category in profile.categories:
            exclude = _shown_names(shown, category) if turn.get("action") == "alternatives" else []
            try:
                found = hybrid_search(
                    self.tk.semantic_search, state.get("message", ""), profile, category,
                    top_k=self.s.candidates_per_category, exclude_names=exclude,
                    fallback=self.tk.fallback_rows,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Search failed for %s: %s", category, exc)
                found = []
            if not found and exclude:
                notes.append(f"{category}: everything that matches has already been shown.")
            if found:
                candidates[category] = found
                note = budget_note(found, profile)
                if note:
                    notes.append(f"{category}: {note}")

        update = {"candidates": candidates, "notes": notes,
                  "steps": turn.get("steps", []) + [{"step": "retrieve", "ms": round((time.monotonic() - started) * 1000)}]}
        if not candidates:
            what = " or ".join(c.lower() for c in profile.categories) or "products"
            if any(_shown_names(shown, c) for c in profile.categories) and turn.get("action") == "alternatives":
                answer = (f"Those are all the {what} options that match what you've told me so far. "
                          f"Want me to loosen something -- the budget, brand or a feature -- to see more?")
            else:
                answer = (f"I couldn't find any {what} matching that right now. Would you like me to widen "
                          f"the search -- a different budget, brand or feature?")
            update.update(action="reply", answer=answer,
                          suggestions=["Increase my budget", "Any brand is fine", "Show all options"])
        return {"turn": update}

    @staticmethod
    def route_after_retrieve(state: ChatState) -> str:
        return "recommend" if (state.get("turn") or {}).get("candidates") else "finalize"

    # -------------------------------------------------------------- recommend
    def recommend(self, state: ChatState) -> dict:
        _status("recommend")
        started = time.monotonic()
        profile = _profile(state)
        turn = state.get("turn") or {}
        candidates: dict = turn.get("candidates") or {}
        n = self.s.picks_per_category

        blocks = []
        for category, rows in candidates.items():
            lines = [f"[{category}]"]
            for i, row in enumerate(rows, start=1):
                scores = row.get("_scores") or {}
                fit = "; ".join(scores.get("reasons") or []) or "no specific signals"
                lines.append(f"{i}. {ctx.product_facts(row, self.s.company_currency)}\n"
                             f"   fit score {scores.get('overall', 0):.2f}: {fit}")
            blocks.append("\n".join(lines))

        try:
            out = self.tk.recommend({
                "company": self.s.company_name,
                "picks_per_category": n,
                "profile": ctx.profile_context(profile),
                "history": ctx.history_context(state.get("messages") or [], self.s.history_window),
                "message": state.get("message", ""),
                "notes": "\n".join(turn.get("notes") or []) or "(none)",
                "candidates": "\n\n".join(blocks),
            })
            message, notes_by_name, suggestions = out.message.strip(), out.picks, out.suggestions
        except Exception as exc:  # noqa: BLE001
            logger.warning("Recommender failed (%s); using ranked picks", exc)
            message, notes_by_name, suggestions = "", [], []

        recommendations, shown_update = [], {}
        for category, rows in candidates.items():
            chosen, narratives = [], {}
            for note in notes_by_name:
                row = match_name(note.name, rows)
                if row is not None and row not in chosen:
                    chosen.append(row)
                    narratives[row["name"]] = note.model_dump()
            # Top up with the best-scored candidates if the model picked fewer.
            for row in rows:
                if len(chosen) >= n:
                    break
                if row not in chosen:
                    chosen.append(row)
            cards = [build_card(r, narratives.get(r["name"]), rank=i, city=profile.city)
                     for i, r in enumerate(chosen[:n], start=1)]
            recommendations.append({"category": category, "picks": cards})
            shown_update[category] = cards

        if not message:
            message = self._fallback_pitch(recommendations)
            suggestions = suggestions or ["Compare the top two", "Anything cheaper?", "Tell me about the first one"]

        return {
            "shown": {**(state.get("shown") or {}), **shown_update},
            "turn": {
                "answer": message,
                "recommendations": recommendations,
                "suggestions": _suggestions(suggestions) or turn.get("suggestions", []),
                "steps": turn.get("steps", []) + [{"step": "recommend", "ms": round((time.monotonic() - started) * 1000)}],
            },
        }

    def _fallback_pitch(self, recommendations: list) -> str:
        lines = ["Here are the best matches I found for you:"]
        for group in recommendations:
            for card in group["picks"]:
                reason = (card.get("fit_reasons") or [""])[0]
                lines.append(f"- **{card['name']}** -- {format_price(card.get('price'), self.s.company_currency)}"
                             + (f" ({reason.lower()})" if reason else ""))
        lines.append("\nWant me to compare any of these, or narrow things down further?")
        return "\n".join(lines)

    # ----------------------------------------------------------------- advise
    def advise(self, state: ChatState) -> dict:
        _status("advise")
        started = time.monotonic()
        profile = _profile(state)
        turn = state.get("turn") or {}
        shown = state.get("shown") or {}
        shown_cards = [c for cards in shown.values() for c in cards or []]

        names = list(dict.fromkeys([*(turn.get("referenced") or []), *_shown_names(shown)]))[:8]
        try:
            rows = self.tk.lookup_products(names)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Product lookup failed (%s); using shown cards", exc)
            rows = []
        by_name = {str(r.get("name")).lower(): r for r in rows}
        for card in shown_cards:  # keep anything the lookup couldn't find
            by_name.setdefault(str(card.get("name")).lower(), card)
        products = list(by_name.values())

        try:
            out = self.tk.advise({
                "company": self.s.company_name,
                "profile": ctx.profile_context(profile),
                "history": ctx.history_context(state.get("messages") or [], self.s.history_window),
                "message": state.get("message", ""),
                "products": "\n".join(ctx.product_facts(p, self.s.company_currency) for p in products)
                            or "(no product data available)",
            })
            message, suggestions = out.message.strip(), out.suggestions
            compare_names, show_names = out.compare_products, out.show_products
        except Exception as exc:  # noqa: BLE001
            logger.warning("Advisor failed (%s)", exc)
            message = ("Sorry, I couldn't look that up just now. Could you ask again, "
                       "or tell me which product you mean?")
            suggestions, compare_names, show_names = [], [], []

        def cards_for(wanted):
            cards = []
            for name in wanted:
                row = match_name(name, products)
                if row is None:
                    continue
                card = row if "specs" in row and isinstance(row.get("specs"), list) else build_card(row, city=profile.city)
                if card.get("name") not in {c.get("name") for c in cards}:
                    cards.append(card)
            return cards

        comparison = cards_for(compare_names)
        return {"turn": {
            "answer": message,
            "comparison": comparison if len(comparison) >= 2 else [],
            "products": [] if len(comparison) >= 2 else cards_for(show_names)[:3],
            "suggestions": _suggestions(suggestions) or turn.get("suggestions", []),
            "steps": turn.get("steps", []) + [{"step": "advise", "ms": round((time.monotonic() - started) * 1000)}],
        }}

    # --------------------------------------------------------------- finalize
    def finalize(self, state: ChatState) -> dict:
        turn = state.get("turn") or {}
        answer = str(turn.get("answer") or "").strip()
        if not answer:
            answer = "Sorry, I lost my train of thought there -- could you say that again?"

        if turn.get("recommendations"):
            response_type = "recommendation"
        elif turn.get("comparison"):
            response_type = "comparison"
        elif turn.get("action") == "clarify":
            response_type = "clarification"
        else:
            response_type = "message"

        return {
            "messages": [
                {"role": "user", "content": state.get("message", "")},
                {"role": "assistant", "content": answer},
            ],
            "turn": {"answer": answer, "response_type": response_type},
        }
