"""
Hybrid retrieval: combines Chroma semantic search with the structured
requirements extracted from the conversation
(AGENTS/REQUIREMENT_EXTRACTOR_AGENT.py) and the recommendation scoring
engine (WORKFLOW/scoring.py), so the product agent gets a ranked,
explainable shortlist instead of "whatever's semantically closest."

The catalog now lives in one shared Chroma collection covering every
category (see DATABASE/SQL_CONNECTOR.py), not a separate collection per
category -- so narrowing to one category at a time is a metadata `filter`
on the search call, not a different vector store object. `category` is
optional here specifically so this module still works for a
category-agnostic search if one is ever needed, but WORKFLOW/ORCHE.py
always passes one for a normal sales turn.

Kept deliberately independent of LangGraph/CrewAI -- it just takes a
LangChain vector store, a query, a requirements dict and an optional
category, and returns plain dicts, so it's easy to unit test without
building a graph or an LLM crew.
"""
import logging
from typing import Optional

from WORKFLOW.scoring import score_candidate

logger = logging.getLogger("agentic_salesman.retrieval")

DEFAULT_TOP_K = 5
# Cast a wider net than we return, so scoring (which considers budget/spec/
# brand, not just semantic closeness) has real room to re-rank -- the top
# semantic match isn't always the best overall fit.
FETCH_MULTIPLIER = 3


def _semantic_candidates(vector_store, query: str, k: int, category: Optional[str] = None) -> list:
    """Returns a list of (Document, relevance) with relevance in [0, 1],
    higher = more relevant, regardless of which similarity API the vector
    store actually supports. Falls back gracefully -- a vector store that
    only implements the plainest `similarity_search` still works, just with
    less precise (rank-based) semantic scores.

    `category`, when given, is passed as a Chroma metadata filter so the
    shared products collection only returns hits from that one category --
    a phone-shaped query never accidentally surfaces a refrigerator."""
    filter_kwargs = {"filter": {"category": category}} if category else {}

    try:
        pairs = vector_store.similarity_search_with_relevance_scores(query, k=k, **filter_kwargs)
        return [(doc, max(0.0, min(1.0, score))) for doc, score in pairs]
    except Exception as exc:  # pragma: no cover - depends on store config
        logger.debug("similarity_search_with_relevance_scores unavailable: %s", exc)

    try:
        pairs = vector_store.similarity_search_with_score(query, k=k, **filter_kwargs)
        if not pairs:
            return []
        distances = [distance for _, distance in pairs]
        low, high = min(distances), max(distances)
        spread = (high - low) or 1.0
        # Chroma's raw "score" here is a distance (lower = closer), so
        # relevance is the inverted min-max normalization of it.
        return [(doc, 1.0 - ((distance - low) / spread)) for doc, distance in pairs]
    except Exception as exc:  # pragma: no cover - depends on store config
        logger.debug("similarity_search_with_score unavailable: %s", exc)

    docs = vector_store.similarity_search(query, k=k, **filter_kwargs)
    count = max(len(docs), 1)
    # No real score available at all -- assign a descending rank-based
    # score so ordering is still meaningful to the scoring engine.
    return [(doc, 1.0 - (i / count)) for i, doc in enumerate(docs)]


def hybrid_search(
    vector_store,
    query: str,
    requirements: Optional[dict] = None,
    top_k: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
) -> list:
    """Returns up to `top_k` candidate products, each a dict of the
    product's fields (from the Chroma document metadata -- i.e. the same
    row data DATABASE/SQL_CONNECTOR.py embedded) plus a "_scores" key
    holding the WORKFLOW/scoring.py breakdown, sorted by overall score
    descending. `category` scopes the search to one category of the shared
    catalog -- see _semantic_candidates."""
    requirements = requirements or {}
    fetch_k = max(top_k * FETCH_MULTIPLIER, top_k)
    semantic_hits = _semantic_candidates(vector_store, query, fetch_k, category=category)

    candidates = []
    seen_names = set()
    for doc, semantic_score in semantic_hits:
        row = dict(doc.metadata or {})
        row.setdefault("_page_content", doc.page_content)
        name = row.get("name")
        if name and name in seen_names:
            continue  # a product can appear more than once if it was
            # embedded before a rebuild; keep only the first (best-ranked).
        if name:
            seen_names.add(name)

        scores = score_candidate(row, requirements, semantic_score)
        candidates.append({**row, "_scores": scores})

    candidates.sort(key=lambda c: c["_scores"]["overall"], reverse=True)
    return candidates[:top_k]


def format_candidates_for_prompt(candidates: list) -> str:
    """Renders candidates as the "RAG Data" text block the sales-crew
    prompts (AGENTS/SALES_CREW_FACTORY.py) already expect -- kept as plain
    prose (not JSON) since that's what the existing prompts were written
    and tested against; the structured version stays available to callers
    as the candidates list itself for the API response / trace."""
    if not candidates:
        return "No matching products were found in the catalog."

    blocks = []
    for rank, candidate in enumerate(candidates, start=1):
        fields = {
            key: value
            for key, value in candidate.items()
            if not key.startswith("_")
        }
        field_text = ", ".join(f"{key}: {value}" for key, value in fields.items())
        score = candidate["_scores"]["overall"]
        blocks.append(f"{rank}. {field_text} (match score: {score:.2f})")
    header = (
        "The products below are already ranked best-to-worst by our scoring "
        "engine (#1 is the best overall match) -- keep this exact order in "
        "your response, do not re-rank or reorder them yourself:\n"
    )
    return header + "\n".join(blocks)
