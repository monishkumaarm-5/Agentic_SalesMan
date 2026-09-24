# Agentic SalesMan

A multi-agent shopping assistant for a retail store's catalog (mobiles,
laptops, TVs, appliances and more). A LangGraph pipeline takes each
customer message through a rule-based entry guard, a Business Need agent,
a RAG-grounded Product Expert agent and a Sales Consultant agent, then a
rule-based exit guard, and returns a Markdown answer plus structured
product cards.

- **Backend** (`backend/`): FastAPI + LangGraph + Gemini, MySQL catalog,
  Chroma vector store, SQLite conversation checkpoints.
- **Frontend** (`FRONTEND/`): React 19 + Vite chat UI.

## Architecture

```
React (FRONTEND/) ──HTTP──▶ FastAPI (backend/APP/main.py)
                                 │   rate limit · optional API key · CORS
                                 ▼
                     ENDPOINTS/endpoints.py   POST /api/chat, /api/compare, ...
                                 ▼
                     WORKFLOW/ORCHE.py (LangGraph, checkpointed per thread)

   guardrail_in ──▶ business_need ──▶ product_expert ──▶ sales_consultant ──▶ guardrail_out
   (rules, no LLM)   (LLM: category,    (hybrid search +   (LLM: pitch, follow-   (rules, no LLM)
                      budget, use case,  LLM picks from      up answers, redirects)
                      psychology)        scored candidates)
                                 ▼
          WORKFLOW/retrieval.py + scoring.py  ◀──  DATABASE/SQL_CONNECTOR.py
          (semantic + budget/spec/brand/rating)     (MySQL `products` ─▶ Chroma)
```

Each agent either hands off to the next one in the same turn or ends the
turn with a question for the customer. Product prices, stock, links and
store availability on the cards always come from the catalog, never from
the LLM.

## Quick start with Docker

```bash
cp backend/.env.example backend/.env   # set GOOGLE_API_KEY at minimum
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

MySQL is seeded from `backend/sql/sample_data_products.sql` (96 products
across 12 categories) plus `add_customer_feedback.sql` on first start.

## Local development

### Backend

Requires Python 3.11+, a reachable MySQL 8 server and a Gemini API key.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.dummy.py config.py      # reads everything from env vars / .env by default
cp .env.example .env              # then fill in real values

mysql -u <user> -p <db_name> < sql/sample_data_products.sql
mysql -u <user> -p <db_name> < sql/add_customer_feedback.sql

uvicorn APP.main:app --reload --port 8000
```

The first chat request embeds the catalog into `WORKFLOW/chroma_db/`.
Later starts reuse it; the index is rebuilt automatically when any
catalog row is added, removed or edited (content fingerprint, see
`DATABASE/SQL_CONNECTOR.py`).

### Frontend

```bash
cd FRONTEND
npm ci
npm run dev        # http://localhost:5173, proxies /api to 127.0.0.1:8000
```

Or start both at once from the repo root: `python start.py`
(`--port 8080` to move the backend; the dev proxy follows it).

### Tests

```bash
cd backend && pytest -q                          # no real LLM/DB calls
cd FRONTEND && npm run lint && npm test && npm run build
```

CI (`.github/workflows/ci.yml`) runs both on every push and pull request.

## Configuration

All settings live in `backend/config.py` (copied from `config.dummy.py`)
and can be supplied as environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | – | Gemini API key (required) |
| `LLM_MODEL` | `gemini-3.1-flash-lite` | Chat model used by every agent |
| `DB_USERNAME` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME` | – | MySQL connection |
| `ALLOWED_ORIGINS` | Vite dev origins | CORS allow-list |
| `API_KEY` | empty (open) | When set, `/api/chat`, `/api/history`, `/api/compare`, `/api/traces` require `X-API-Key` |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per-IP limit on `/api/*` (health excluded); `0` disables |
| `REQUEST_TIMEOUT_SECONDS` | `90` | Hard ceiling per chat turn (504 after) |
| `COMPANY_NAME`, `COMPANY_WEBSITE`, ... | Trein placeholders | Store identity; store locations are in `config.py` |

The frontend reads `VITE_API_BASE_URL` (defaults to `/api`) and
`VITE_API_KEY` at build time; see `FRONTEND/.env.example`.

## API

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/chat` | `{question, thread_id?}` → answer, `response_type`, `product` cards, scored `candidates`, `confidence` |
| `GET` | `/api/history/{thread_id}` | Conversation turns |
| `POST` | `/api/compare` | LLM-free side-by-side comparison of 2–10 products |
| `GET` | `/api/categories` | Live category list |
| `GET` | `/api/company` | Store identity and locations |
| `GET` | `/api/traces` | Per-turn routing/decision log |
| `GET` | `/api/health` | Config + DB readiness (never rate-limited) |

`backend/MCP/server.py` exposes the same catalog tools to MCP clients.

## Production notes

- The rate limiter and conversation checkpoints are per-process. Run one
  worker, or move them to Redis/Postgres before scaling out. Behind a
  reverse proxy every client shares the proxy's IP unless the proxy
  forwards real client addresses to uvicorn (`--proxy-headers`).
- Set `API_KEY` before exposing the API publicly. Note that a key baked
  into the frontend build (`VITE_API_KEY`) is visible to anyone who loads
  the page, so it only deters casual use.
- `WORKFLOW/ORCHE_crewai_legacy.py` and `AGENTS/SALES_CREW_FACTORY.py`
  (plus the older guard/extractor agents) are the previous CrewAI
  pipeline, kept for reference and not used by the live API.
