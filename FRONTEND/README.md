# Agentic SalesMan -- Frontend

A React (Vite) chat UI for the Agentic SalesMan multi-agent backend. See the
[project root README](../README.md) for the full setup (backend + frontend).

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

## Configuration

If the backend is hosted somewhere other than the dev proxy target, copy
`.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the backend's
full `/api` URL before building.

## Structure

```
src/
  api.js                  fetch wrapper for POST /api/chat
  App.jsx                 chat state (messages, thread id, sending state)
  components/
    ChatMessage.jsx        renders one bubble (Markdown for assistant replies)
    ChatInput.jsx           the message composer
```
