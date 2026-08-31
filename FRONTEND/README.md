# Agentic SalesMan -- Frontend

A React (Vite) chat UI for the Agentic SalesMan multi-agent backend. See the
[project root README](../README.md) for the full setup (backend + frontend
+ Docker).

## Quick start

```bash
npm install
npm run dev
```

Open http://127.0.0.1:5173. The dev server proxies `/api/*` to
`http://127.0.0.1:8000` (see `vite.config.js`), so it expects the FastAPI
backend to be running on port 8000.

## Scripts

- `npm run dev` -- start the Vite dev server with hot reload
- `npm run build` -- production build to `dist/`
- `npm run preview` -- preview the production build locally
- `npm run lint` -- run Oxlint
- `npm test` -- run the Vitest suite (37 tests)

## Configuration

Copy `.env.example` to `.env.local` and set, as needed:

- `VITE_API_BASE_URL` -- only needed if the backend is hosted somewhere
  other than the dev proxy target / default relative `/api` path
- `VITE_API_KEY` -- only needed if the backend has `API_KEY` set (see
  `config.dummy.py` in the project root); sent as an `X-API-Key` header on
  every request

## Features

- Chat with the multi-agent backend, with Markdown-rendered assistant
  replies
- Structured product recommendations render as a card (name, reason, key
  features, buy link) below the assistant's message, whether the answer
  covers one category or several
- A "Confidence" badge reflects the backend's exit-evaluator score for that
  answer
- A collapsible "Why these picks" panel shows the scored retrieval
  shortlist (semantic/budget/spec/rating/brand breakdown) behind each
  answer, with a "Compare top matches" action that renders a side-by-side
  spec table via `POST /api/compare`
- Conversation (messages + thread id) persists to `localStorage` across
  refreshes; "New conversation" clears it and starts fresh

## Structure

```
src/
  api.js                        fetch wrapper: sendMessage, fetchHistory, compareProducts
  App.jsx                       chat state, localStorage persistence
  components/
    ChatMessage.jsx              renders one bubble (Markdown + confidence + product card)
    ChatInput.jsx                 the message composer
    ProductCard.jsx               single/multi-category product card(s)
    CandidateScores.jsx           "why these picks" shortlist + compare action
    ComparisonTable.jsx           side-by-side product comparison table
  test/setup.js                  Vitest + Testing Library setup
```
