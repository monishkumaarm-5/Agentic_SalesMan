# Agentic SalesMan

A multi-agent sales assistant for phones, laptops and headphones. A
LangGraph pipeline routes each customer question through an entry guard,
a product-category "sales crew" (CrewAI agents backed by a Chroma RAG store
over your MySQL catalog), and an exit guard, then returns a Markdown answer.

The project has two parts:

- **Backend** (`APP/`, `ENDPOINTS/`, `WORKFLOW/`, `AGENTS/`, `DATABASE/`) --
  a FastAPI service that exposes the agent pipeline over HTTP.
- **Frontend** (`FRONTEND/`) -- a React (Vite) chat UI that talks to the
  backend.

## Architecture

```
React (FRONTEND/)  --HTTP-->  FastAPI (APP/main.py)
                                   |
                              ENDPOINTS/endpoints.py  (POST /api/chat)
                                   |
                              WORKFLOW/ORCHE.py  (LangGraph)
                                   |
              entry guard -> [mobile | laptop | headphone] agents -> exit guard
                                   |
                    DATABASE/SQL_CONNECTOR.py (MySQL -> Chroma RAG)
```

## 1. Backend setup

### Prerequisites

- Python 3.11+
- A MySQL server reachable from this machine
- A Google Gemini API key

### Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

`config.py` is gitignored (it holds secrets), so create your own from the
template:

```bash
cp config.dummy.py config.py
```

Then edit `config.py` with your real values:

- `GOOGLE_API_KEY` -- your Gemini API key
- `DB_USERNAME` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME` -- your
  MySQL credentials
- `ALLOWED_ORIGINS` -- comma-separated origins the API accepts browser
  requests from (defaults already cover the Vite dev server on port 5173)

### Load the sample catalog (first time only)

`Sample_data- practice.txt` contains the `retail_shop` schema and seed data
(phones, laptops, headphones). Load it into MySQL, e.g.:

```bash
mysql -u <username> -p < "Sample_data- practice.txt"
```

The first request to the API will embed these rows into the Chroma vector
store under `WORKFLOW/chroma_db/`. Later runs reuse that store instead of
re-embedding.

### Run

From the project root (so the `AGENTS.*` / `DATABASE.*` / `WORKFLOW.*`
imports resolve):

```bash
uvicorn APP.main:app --reload --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health
- Chat endpoint: `POST http://127.0.0.1:8000/api/chat`
  ```json
  { "question": "recommend a laptop for coding", "thread_id": "optional" }
  ```

## 2. Frontend setup

```bash
cd FRONTEND
npm install
npm run dev
```

Open http://127.0.0.1:5173 -- the dev server proxies `/api/*` straight to
`http://127.0.0.1:8000`, so no extra configuration is needed as long as the
backend is running on port 8000.

To build for production:

```bash
npm run build
```

This outputs static files to `FRONTEND/dist/`. If the backend is hosted at a
different origin than the frontend in production, set `VITE_API_BASE_URL`
(see `FRONTEND/.env.example`) before building, and make sure the backend's
`ALLOWED_ORIGINS` includes the frontend's deployed origin.

## Notes on what changed while wiring this up

- `WORKFLOW/ORCHE.py` used to run the graph once at import time and print
  the answer; it now exposes `ask(question, thread_id)`, builds the graph
  and vector store lazily/once, and fixes a bug where a query judged
  "relevant" but not matched to a category would crash the router.
- The exit guard agent (previously an unimplemented stub) is now wired into
  the graph: every sales-agent answer is checked before it's returned, and a
  failed check replaces the answer with the standard decline message.
- `DATABASE/SQL_CONNECTOR.py` now skips re-embedding a product table into
  Chroma if that collection already has vectors, so repeated backend
  restarts during development don't keep duplicating the RAG data.
