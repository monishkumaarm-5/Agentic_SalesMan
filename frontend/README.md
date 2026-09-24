# Frontend

React 19 + Vite chat UI for the shopping assistant.

```bash
npm ci
npm run dev      # http://localhost:5173, proxies /api to 127.0.0.1:8000
npm run lint && npm test && npm run build
```

```
src/
  api/client.js          REST + streaming (SSE) client
  hooks/                 useChat (conversation state), useTheme, useAutoScroll, useLocalStorage
  components/layout/     Header, ErrorBoundary, Icons
  components/chat/       Welcome, Message, Markdown, StatusIndicator, QuickReplies, ProfileBar, Composer
  components/products/   ProductCard, RecommendationGroup, ProductDetails, CompareTable, CompareTray, Modal
  utils/                 formatting, relative comparison, catalog-driven starter prompts
  styles/                design tokens (light/dark), base, chat, products
```

Build-time settings (see `.env.example`): `VITE_API_BASE_URL` (default `/api`)
and `VITE_API_KEY` (only if the backend sets `API_KEY`).
