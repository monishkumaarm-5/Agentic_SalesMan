# Agentic SalesMan — Multi-Agent AI Commerce Assistant

An agentic sales assistant for **phones, laptops and headphones**, built with
**LangGraph, CrewAI, hybrid SQL+vector RAG, MCP, FastAPI and React**.

Agentic SalesMan doesn't just answer questions from a vector store. It routes
each customer message through an entry guard, extracts structured
requirements (budget, use case, brand) from the conversation, retrieves and
*scores* candidate products with a hybrid SQL + semantic search, hands the
shortlist to a 4-agent CrewAI sales crew, and runs the result through a
5-dimension scored evaluator that can trigger one automatic retry before a
weak or ungrounded answer ever reaches the customer. Every turn is logged to
a queryable execution trace.

---

## Key Features

- Multi-agent architecture: LangGraph orchestrates entry guard → requirement
  extraction → hybrid retrieval → CrewAI sales crew → scored evaluator, with
  conversation memory persisted per thread.
- One CrewAI crew per product category (phone / laptop / headphone), each a
  4-agent pipeline (product expert → consumer psychologist → storyteller →
  sales consultant) sharing one factory (`AGENTS/SALES_CREW_FACTORY.py`).
- Hybrid SQL + vector RAG: MySQL structured filters combine with Chroma
  semantic search, then every candidate is scored (semantic relevance,
  budget fit, spec match, rating when available, brand fit) and ranked --
  see `WORKFLOW/retrieval.py` + `WORKFLOW/scoring.py`.
- A real tool layer (`TOOLS/product_tools.py`): search, product detail
  lookup, comparison, inventory and price-check functions, callable by the
  CrewAI product agent in-process *and* exposed to any MCP client via a
  standalone MCP server (`MCP/server.py`).
- A scored exit evaluator (groundedness, relevance, product accuracy,
  constraint satisfaction, sales quality) that triggers one automatic retry
  of the sales crew -- with the evaluator's own feedback appended -- before
  falling back to a safe decline.
- Multi-category fan-out ("a phone and headphones that go well together")
  and greeting/small-talk handling, both routed by the entry guard.
- Product comparison as a first-class, LLM-free API (`POST /api/compare`)
  and a UI action ("Compare top matches").
- Conversation memory via a LangGraph SQLite checkpointer, keyed by
  `thread_id`, surviving backend restarts.
- Execution tracing (`WORKFLOW/tracing.py` + `GET /api/traces`): routing,
  retrieval candidates/scores, evaluator scores, retries and latency per
  turn, in a queryable SQLite log.
- Opt-in API-key auth, per-IP rate limiting, a request timeout with a clean
  504, and a real `/api/health` that checks config + DB connectivity.
- FastAPI backend, React (Vite) frontend, 153 automated tests (116 backend +
  37 frontend), a GitHub Actions CI pipeline, and Docker/docker-compose for
  a one-command full-stack run.

---

## Architecture

```
                         React (FRONTEND/)
                              |
                              | HTTP
                              v
                          FastAPI (APP/main.py)
                     [ API key auth | rate limit ]
                              |
                    ENDPOINTS/endpoints.py
        /api/chat  /api/compare  /api/history  /api/traces  /api/health
                              |
                              v
                      WORKFLOW/ORCHE.py (LangGraph)
                              |
                        entry_guard_agent
                     (relevance / greeting / category)
                              |
              +---------------+----------------+
              |               |                |
           chatbot         greeting        sales_agents
          (decline)       (canned)              |
              |               |          requirement extraction
              |               |     (AGENTS/REQUIREMENT_EXTRACTOR_AGENT.py)
              |               |                |
              |               |          hybrid retrieval + scoring
              |               |     (WORKFLOW/retrieval.py + scoring.py)
              |               |                |
              |               |         CrewAI sales crew(s)
              |               |    (AGENTS/SALES_CREW_FACTORY.py, w/ tools)
              |               |                |
              +---------------+----------------+
                              |
                       exit_guard_agent
                (AGENTS/EXIT_SAFE_GAURD_AGENT.py -- scored
                 evaluator, one retry on failure)
                              |
                              v
                  history persisted (SqliteSaver)
                  trace persisted (WORKFLOW/tracing.py)

        TOOLS/product_tools.py  <-- shared by -->  MCP/server.py
       (search / details / compare /                (standalone MCP
        inventory / price, MySQL-backed)              server, stdio)
```

---

## Agentic Workflow, Walked Through

Example: *"I need a laptop under ₹80,000 for Python, Docker and some
machine learning."*

**1. Entry guard** (`AGENTS/ENTRYSAFEGAURD_AGENT.py`) classifies the message:
relevant, not a greeting, category = laptop.

**2. Requirement extraction** (`AGENTS/REQUIREMENT_EXTRACTOR_AGENT.py`) pulls
structured requirements out of the conversation:

```json
{
  "budget_max": 80000,
  "use_cases": ["python", "docker", "machine learning"],
  "brand": null
}
```

**3. Hybrid retrieval** (`WORKFLOW/retrieval.py`) fetches semantic
candidates from Chroma, then `WORKFLOW/scoring.py` scores each one:

```
overall = semantic * 0.30 + budget_fit * 0.25 + spec_match * 0.20
          + rating * 0.15 + brand_fit * 0.10
```

(The sample catalog has no rating column, so that weight is redistributed
proportionally across the other four rather than faked -- see the module
docstring for why.) A candidate whose price blows the budget or whose RAM
doesn't fit the "machine learning" use case drops down the ranking even if
it was the closest semantic match.

**4. Sales crew** (`AGENTS/SALES_CREW_FACTORY.py`) gets the scored shortlist
as its "RAG data" and produces a recommendation, backed by
search/compare/inventory/price tools it can call for anything the shortlist
doesn't cover.

**5. Exit evaluator** (`AGENTS/EXIT_SAFE_GAURD_AGENT.py`) scores the answer
on 5 dimensions. A hallucinated spec or an answer that ignores the ₹80,000
budget fails the evaluator -- the crew gets one retry with the evaluator's
own reasons appended as feedback before the pipeline falls back to a decline.

**6. Trace recorded.** Every one of the above steps -- extracted
requirements, ranked candidates, evaluator scores, retry count, latency --
is written to the execution trace, queryable via `GET /api/traces`.

---

## Hybrid RAG

```
                    User Query
                        |
                        v
             Requirement Extraction (LLM)
                        |
            +-----------+-----------+
            |                       |
            v                       v
      Structured filters      Semantic query
    (budget, min RAM, brand)         |
            |                       v
            v                  Chroma (vector)
     TOOLS/product_tools.py         |
      .search_products()            |
            |                       |
            +-----------+-----------+
                        v
              WORKFLOW/scoring.py
           (semantic + budget + spec
            + rating + brand -> overall)
                        |
                        v
              Ranked candidate list
           (surfaced in the API response
            as `candidates`, and in the
            trace log)
```

Structured filtering and semantic search are two separate paths that meet at
scoring, rather than one replacing the other: `search_products` gives exact
price/spec/brand filtering (see `TOOLS/product_tools.py`), Chroma gives
semantic understanding of phrases like "good for machine learning," and
`score_candidate` combines both into one ranked, explainable list.

---

## Specialized Agents

Each category (phone / laptop / headphone) gets its own 4-agent CrewAI crew
from the same factory (`AGENTS/SALES_CREW_FACTORY.py`):

1. **Product Expert** -- compares available products from the scored
   shortlist, recommends one, returns structured JSON (name, reason, key
   features, buy link). Has `search_*`, `compare_*`, `check_*_inventory` and
   `get_*_price` tools for anything the shortlist doesn't cover.
2. **Consumer Psychologist** -- infers buying intent, pain points and
   urgency from the request.
3. **Storytelling Expert** -- writes a short, honest, non-exaggerated story
   connecting the product to the customer's stated need.
4. **Sales Consultant** -- composes the final Markdown answer from the
   above three outputs, never inventing links or specs.

A question spanning more than one category ("a phone and headphones that go
well together") runs each category's crew and composes the results into one
answer (`sales_agents` node in `WORKFLOW/ORCHE.py`).

---

## Tool Layer

`TOOLS/product_tools.py` holds five framework-agnostic functions backed
directly by MySQL:

```python
search_products(category, max_price=None, min_ram_gb=None, ...)
get_product_details(category, product_name)
compare_products(category, product_names)
check_inventory(category, product_name)
get_current_price(category, product_name)
```

They're called from two directions:

- **In-process**, by the CrewAI product agent (`AGENTS/SALES_CREW_FACTORY.py`
  wraps each one with `@tool` and scopes it to that agent's category) -- no
  extra network hop per chat turn.
- **Over MCP**, by any external MCP client, via the standalone server in
  `MCP/server.py` (`python -m MCP.server`, stdio transport). Same
  functions, same behavior, reachable from Claude Desktop, Claude Code, or
  another agent entirely, without maintaining a second implementation.

`check_inventory` is deliberately honest about a real limitation: the
sample catalog has no dedicated stock/quantity column, so it reports
catalog presence (with a `"source": "catalog-presence"` flag) unless a real
`stock`/`quantity`/`available` column exists, in which case that's used
instead.

---

## MCP Integration

```
             Any MCP client
   (Claude Desktop, Claude Code, another agent)
                    |
                    v
          MCP/server.py (FastMCP, stdio)
                    |
     search_products_tool / get_product_details_tool
     compare_products_tool / check_inventory_tool
     get_current_price_tool
                    |
                    v
          TOOLS/product_tools.py
                    |
                    v
                  MySQL
```

Run it: `python -m MCP.server` from the project root. Point an MCP client
at it with a config like:

```json
{
  "mcpServers": {
    "agentic-salesman": {
      "command": "python",
      "args": ["-m", "MCP.server"],
      "cwd": "/path/to/Agentic_SalesMan"
    }
  }
}
```

This server does **not** sit in the hot path of a chat request -- the
CrewAI agents call the same underlying functions in-process for latency
(see Tool Layer above). It's there so the catalog is reachable over the
protocol too, without a second implementation to keep in sync.

---

## Conversation Memory

Each conversation keeps a `thread_id`. LangGraph's `SqliteSaver`
checkpointer persists the accumulated `history` field across turns *and*
backend restarts (`WORKFLOW/checkpoints.sqlite` by default):

```
User: I need a laptop.
Agent: [asks clarifying questions if needed]
User: Around ₹70,000, for programming, I prefer Lenovo.
```

The next turn's requirement extraction sees the full recent history (not
just the latest message), so a bare follow-up like "under $1000" after
"recommend a laptop" still resolves against the right category and intent.
Retrieve it directly via `GET /api/history/{thread_id}`.

---

## Guardrails

**Entry guard** (`AGENTS/ENTRYSAFEGAURD_AGENT.py`) -- classifies each
message before anything else runs: relevant vs. off-topic/prompt-injection,
greeting vs. product question, and which category(ies) apply. Off-topic
requests are declined before any retrieval or crew work happens.

**Exit evaluator** (`AGENTS/EXIT_SAFE_GAURD_AGENT.py`) -- scores every
sales-agent answer on groundedness, relevance, product accuracy, constraint
satisfaction and sales quality (0-1 each). Groundedness and product accuracy
are a *hard gate*: a well-written but hallucinated recommendation fails
regardless of how the other three score. Both guards fail open on their own
LLM call erroring (a broken evaluator shouldn't be able to take down the
whole chat).

---

## Evaluation Loop

```
        Sales crew answer
               |
               v
        Exit evaluator (5 scores)
               |
        +------+------+
        |             |
      PASS          FAIL
        |             |
        v             v
    Response    Retry once, with
                 evaluator's reasons
                 appended as feedback
                        |
                 +------+------+
                 |             |
               PASS          FAIL
                 |             |
                 v             v
             Response      Decline
```

`ENABLE_EVALUATOR_RETRY` (default on) and `EVALUATION_MIN_SCORE` (default
`0.6`) are both configurable -- see `config.dummy.py`.

---

## Observability

Every chat turn writes a trace record (`WORKFLOW/tracing.py`, a small
SQLite table) covering: the question, detected category/categories,
extracted requirements, retrieval candidates with their full score
breakdown, evaluator scores + pass/fail + retry count, and latency. Query it
via `GET /api/traces?thread_id=...&limit=20`.

This is a lightweight, local, SQLite-backed log -- good for debugging a
local/portfolio deployment. A real production deployment would ship these
same events to OpenTelemetry/a real tracing backend instead; see Future
Improvements.

---

## Backend Structure

```
APP/
  main.py                  FastAPI app, CORS, rate-limit middleware, lifespan logging
  auth.py                  optional X-API-Key dependency
  rate_limit.py             per-IP sliding-window middleware
ENDPOINTS/
  endpoints.py              /api/health /api/chat /api/compare /api/history /api/traces
WORKFLOW/
  ORCHE.py                  LangGraph pipeline (entry guard -> ... -> exit evaluator)
  retrieval.py               hybrid SQL+vector search
  scoring.py                  recommendation scoring engine
  tracing.py                   execution trace log
AGENTS/
  ENTRYSAFEGAURD_AGENT.py    entry guard
  REQUIREMENT_EXTRACTOR_AGENT.py  structured requirement extraction
  SALES_CREW_FACTORY.py      shared 4-agent crew builder + tools
  MOBILE_/LAPTOP_/HEADPHONE_SALES_AGENT.py  thin per-category wrappers
  EXIT_SAFE_GAURD_AGENT.py   scored exit evaluator
TOOLS/
  product_tools.py           search / details / compare / inventory / price
MCP/
  server.py                  standalone MCP server exposing the tools above
DATABASE/
  SQL_CONNECTOR.py            MySQL -> Chroma sync, shared engine builder
FRONTEND/
  src/                        React (Vite) chat UI
tests/                        116 backend tests (pytest)
```

---

## API

### Health

```http
GET /api/health
```
Never raises; reports whether Gemini/DB config looks filled in and whether
MySQL is reachable. No auth required.

### Chat

```http
POST /api/chat
{ "question": "recommend a laptop for coding under 70000", "thread_id": "optional" }
```

```json
{
  "answer": "...",
  "context": "LAPTOP",
  "thread_id": "...",
  "product": { "recommended_product": "...", "reason": "...", "key_features": [], "buy_link": "..." },
  "candidates": { "LAPTOP": [ { "name": "...", "price": 72999, "_scores": { "overall": 0.88, "...": "..." } } ] },
  "confidence": 0.85
}
```

### Compare

```http
POST /api/compare
{ "category": "laptop", "product_names": ["Lenovo LOQ", "HP Pavilion"] }
```
Deterministic, no LLM call -- reads straight from MySQL.

### History / Traces

```http
GET /api/history/{thread_id}
GET /api/traces?thread_id=optional&limit=20
```

`/api/chat`, `/api/compare` and `/api/history` require an `X-API-Key`
header when `API_KEY` is configured; `/api/health` never does.

---

## Frontend

React (Vite) chat UI (`FRONTEND/`): Markdown answers, a confidence badge per
answer, product cards, a collapsible "Why these picks" panel with a
"Compare top matches" action, `localStorage` chat persistence, and an
optional API-key header. See `FRONTEND/README.md` for details.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | FastAPI |
| Orchestration | LangGraph |
| Multi-agent crews | CrewAI |
| LLM | Google Gemini (`gemini-3.5-flash-lite`) |
| Vector store | Chroma |
| Relational DB | MySQL |
| Tool protocol | MCP (Model Context Protocol) |
| Conversation memory | LangGraph `SqliteSaver` |
| Execution tracing | SQLite |
| CI | GitHub Actions |
| Containerization | Docker / docker-compose |

---

## Running the Project

### 1. Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.dummy.py config.py     # then fill in GOOGLE_API_KEY + DB_* credentials
```

Load `Sample_data- practice.txt` into MySQL (schema + seed data), then:

```bash
uvicorn APP.main:app --reload --port 8000
```

- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

Config reference (all except `GOOGLE_API_KEY`/`DB_*` have working defaults
-- see `config.dummy.py` for the full list including auth, rate limiting,
timeouts, evaluator threshold/retry, and trace/checkpoint paths).

### 2. Frontend

```bash
cd FRONTEND
npm install
npm run dev
```
Open http://127.0.0.1:5173 (proxies `/api/*` to port 8000 in dev).

### 3. MCP server (optional, standalone)

```bash
python -m MCP.server
```

### 4. Tests

```bash
pytest -v                 # 116 backend tests
cd FRONTEND && npm test    # 37 frontend tests
```

Everything is mocked (no real LLM/DB/MySQL calls) -- `conftest.py` sets
placeholder env vars and a throwaway `config.py` automatically, so `pytest`
works out of the box in CI or a fresh clone.

### 5. Docker

```bash
cp .env.example .env      # fill in GOOGLE_API_KEY at minimum
# rename your copy of "Sample_data- practice.txt" to db-init.sql, place it
# next to docker-compose.yml, so MySQL loads it on first start
docker compose up --build
```
Frontend: http://localhost:5173 · Backend docs: http://localhost:8000/docs

### 6. CI

`.github/workflows/ci.yml` runs the backend (`pytest`) and frontend
(`oxlint`, `vitest`, `vite build`) suites on every push/PR to `main`.

---

## Future Improvements

Genuinely not built yet -- called out here rather than implied by the
feature list above:

- Order creation, cart management, payment integration, real-time
  inventory (a real stock table + write path, not the catalog-presence
  fallback `check_inventory` uses today)
- Customer profiles, personalized recommendations, sales analytics
  dashboard, A/B testing for sales prompts
- User accounts / OAuth-style authentication and authorization (today's
  auth is a single shared `API_KEY`, not per-user)
- Redis-backed conversation state and rate limiting (today: SQLite +
  in-memory, both fine for a single-process deployment, not for horizontal
  scaling)
- PostgreSQL as an alternative to MySQL for the product catalog
- OpenTelemetry-based distributed tracing (today: a local SQLite trace log
  -- see Observability above)
- Distributed/multi-tenant MCP servers
- Cross-selling/upselling logic (the agents recommend within the category
  asked about; they don't yet suggest complementary categories)

---

## Why This Project

Agentic SalesMan is built to demonstrate how the pieces of a modern agentic
system fit together in one working, tested codebase: multi-agent
orchestration (LangGraph + CrewAI), hybrid retrieval over structured and
unstructured data, an explainable scoring engine, a real tool layer exposed
both in-process and over MCP, guardrails on both ends of the pipeline, a
scored evaluator with automatic retry, persistent memory, and execution
tracing -- backed by 153 automated tests, a CI pipeline, and a Docker
Compose stack, not just a single LLM call wrapped in a chat UI.

### Portfolio highlights

**AI/agent engineering** -- multi-agent architecture (LangGraph + CrewAI)
with category-based routing; hybrid SQL + vector retrieval with an
explainable recommendation-scoring formula; a scored, 5-dimension exit
evaluator with automatic retry; a real tool layer exposed both in-process
and via a standalone MCP server.

**Backend engineering** -- async FastAPI service with modular
database/agent/workflow layers; opt-in auth, rate limiting, request
timeouts, real health checks, structured logging, and a queryable
execution-trace log.

**Full-stack engineering** -- React/Vite conversational UI wired to all of
the above (confidence scores, scored candidate shortlists, live product
comparison), with `localStorage` persistence and production-style
error/loading states.

**Delivery** -- 153 automated tests (pytest + Vitest), GitHub Actions CI,
and a Docker Compose stack for a one-command local run.
