# Agentic SalesMan

An AI shopping assistant for a retail store. Customers describe what they
need in their own words; a LangGraph workflow of Gemini agents works out
what they want, searches the real catalog, and replies with an honest pitch,
product cards, comparisons and quick replies, showing its progress live.

```
backend/    FastAPI + LangGraph + Gemini, MySQL catalog, Chroma semantic index
frontend/   React 19 + Vite chat UI (light/dark, streaming progress, compare, details)
```

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env    # set GOOGLE_API_KEY at minimum
docker compose up --build
```

Open http://localhost:5173 (API docs at http://localhost:8000/docs). MySQL is
seeded with 96 sample products across 12 categories on first start.

## Local development

```bash
# backend (needs MySQL; load backend/sql/seed/*.sql once)
cd backend
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload

# frontend
cd frontend
npm ci
npm run dev
```

Or run both with `python start.py` from the repository root.

## What makes it tick

- **Dynamic understanding**: one agent reads each message against the
  whole conversation, the live catalog and the store info, then decides
  whether to chat, ask one focused question, recommend, show alternatives
  or answer about specific products. No keyword lists or fixed scripts.
- **Grounded recommendations**: candidates come from hybrid search over the
  catalog and are scored transparently (budget, requested features, rating,
  brand, availability). The agent only picks among them, and every price,
  spec, stock level and store on a card comes from the database.
- **Visible memory**: the UI shows what the assistant has understood
  ("Mobile · Under ₹30k · 5G · Chennai"), and suggests next replies.
- **Resilient**: every LLM step has a fallback, turns stream progress,
  time out cleanly, and are traced for debugging.

See `backend/README.md` and `frontend/README.md` for details.

## Tests

```bash
cd backend && pytest && ruff check app tests
cd frontend && npm run lint && npm test && npm run build
```

CI runs both on every push and pull request.

## Production notes

- Rate limiting and conversation checkpoints are per-process; use one
  worker, or move them to Redis/Postgres before scaling out.
- Set `API_KEY` before exposing the API. A key baked into the frontend
  build is visible to anyone who loads the page.
