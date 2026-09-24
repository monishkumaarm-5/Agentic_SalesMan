# Backend

FastAPI + LangGraph + Gemini. Run from this directory:

```bash
pip install -r requirements-dev.txt
cp .env.example .env            # set GOOGLE_API_KEY and MySQL credentials
uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest && ruff check app tests
```

## Layout

```
app/
  main.py              FastAPI app factory
  api/                 routes, request/response schemas, API key + rate limiting
  core/                settings (env / .env), logging
  agents/              the three LLM agents + prompt context builders
    understanding.py     reads each message, updates the shopping profile, picks the next action
    recommender.py       chooses picks from scored candidates and writes the pitch
    advisor.py           answers product questions and comparisons from catalog data
  graph/               LangGraph workflow: state, nodes, builder, toolkit (swappable dependencies)
  catalog/             MySQL access, semantic index (Chroma), data-driven completeness, catalog tools
  retrieval/           hybrid search, explainable scoring, product cards
  services/            chat service (sync + streaming, timeouts, per-thread locking), tracing
  company.py           store identity and showroom matching
  mcp_server.py        catalog tools over the Model Context Protocol
  data/stores.json     showroom locations
sql/                   seed data, migrations, handy queries
airflow/               daily index sync DAG
tests/                 pytest suite (no real LLM or database calls)
```

## How a turn works

```
guard ─▶ understand ─┬─▶ finalize                          reply / clarify
                     ├─▶ retrieve ─▶ recommend ─▶ finalize  recommend / alternatives
                     └─▶ advise ─▶ finalize                discuss (questions, comparisons)
```

- **understand** (LLM) sees the conversation, the live catalog (categories,
  price ranges, brands), the store info and the products already shown. It
  returns the full updated shopping profile, the next action, the reply for
  conversational turns, and quick-reply suggestions. There are no keyword
  lists or fixed question counts; the code only enforces a few invariants
  (can't recommend without a category, can't discuss products nobody has
  seen, and at most `MAX_CLARIFYING_QUESTIONS` questions in a row).
- **retrieve** runs semantic search per category and re-ranks with
  `retrieval/scoring.py`: relevance, budget, the customer's own requested
  features, rating, brand preference and availability. Missing signals are
  dropped, not penalised. "Alternatives" exclude products already shown.
- **recommend** (LLM) picks from those real candidates and writes the pitch.
  Picks are mapped back to catalog rows, so prices, stock, stores and specs
  on the cards always come from the catalog.
- **advise** (LLM) answers from full catalog data (including reviews) and
  can ask the UI to show a side-by-side comparison.

Every LLM step has a fallback, so a model outage degrades the answer instead
of failing the turn. Each turn's decisions are stored (`GET /api/traces`).

## Logs

With `LOG_GRAPH_STATE=true` (default) the server log shows the workflow graph
at startup, then for every turn: each node with the state it received, the
agent it used, what it returned and how long it took, every routing
decision, every LLM call (agent, model, latency, parsed output) and a
one-line turn summary. A timeout logs which step was still running.
`LOG_LLM_PROMPTS=true` adds the full prompts.

The semantic search index is built in a background thread at startup; until
it's ready (first run downloads the embedding model), searches rank products
straight from MySQL by keyword overlap, so chats never wait on it.
`GET /api/health` reports `search_index: building | ready | failed`.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/chat` | `{message, thread_id?}` → answer, `response_type`, `recommendations`, `comparison`, `products`, `suggestions`, `profile`, `confidence` |
| POST | `/api/chat/stream` | Same, as server-sent events: `start`, `status`…, then `final` or `error` |
| GET | `/api/threads/{id}/history` | Conversation turns |
| GET | `/api/categories` | Live categories with counts, price ranges, brands |
| GET | `/api/company` | Store identity and showrooms |
| POST | `/api/compare` | Raw side-by-side catalog data for 2–6 products |
| GET | `/api/products/search` | Structured catalog search |
| GET | `/api/traces` | Per-turn decision log |
| GET | `/api/health` | Readiness (never rate-limited, never needs a key) |

When `API_KEY` is set, everything except health, categories and company
requires an `X-API-Key` header.

## Catalog

One `products` table; category-specific specs live in a JSON `attributes`
column, so new categories need no code. The index rebuilds automatically
whenever catalog rows change. Specs that most products in a category have
are "expected" for that category (learned from the data); a product missing
some is filled from its description when possible and still indexed.
