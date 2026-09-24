# Agentic_SalesMan — Frontend Source


## `.env.example`

```bash
# Only needed if the FastAPI backend is hosted somewhere other than the Vite
# dev proxy target (http://127.0.0.1:8000). Copy this file to .env.local and
# set a full URL, e.g. VITE_API_BASE_URL=https://api.example.com/api
# VITE_API_BASE_URL=/api

# Only needed if the backend has API_KEY set (see config.dummy.py). Must
# match the backend's API_KEY exactly.
# VITE_API_KEY=
```


## `.gitignore`

```text
# Logs
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

node_modules
dist
dist-ssr
*.local

# Editor directories and files
.vscode/*
!.vscode/extensions.json
.idea
.DS_Store
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
```


## `.oxlintrc.json`

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "oxc"],
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```


## `Dockerfile`

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```


## `README.md`

```markdown
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
```


## `index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="AI-powered multi-agent shopping assistant" />
    <meta name="theme-color" content="#0b0d11" />
    <title>Trein — AI Shopping Assistant</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;650;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```


## `nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Single-page app: any path that isn't a real static file falls back to
    # index.html so client-side routing (and a plain refresh) works.
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls to the backend container. This is what lets the
    # frontend keep using its default relative "/api" base URL (see
    # src/api.js) with no VITE_API_BASE_URL build arg needed, as long as
    # both containers run together via docker-compose.yml, where the
    # backend service is reachable at the hostname "backend".
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```


## `package.json`

```json
{
  "name": "agentic-salesman-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "react-markdown": "^10.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.6",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.4",
    "jsdom": "^30.0.1",
    "oxlint": "^1.75.0",
    "vite": "^8.2.0",
    "vitest": "^4.1.11"
  }
}
```


## `public/favicon.svg`

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Chat logo">
  <defs>
    <!-- ── Base tile: mint → emerald → deep jade ── -->
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#6ee7b7"/>
      <stop offset="45%"  stop-color="#10b981"/>
      <stop offset="100%" stop-color="#065f46"/>
    </linearGradient>

    <!-- ── Champagne gold accent (smile, clasp, rim) ── -->
    <linearGradient id="champagne" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#fff5db"/>
      <stop offset="55%"  stop-color="#f0d9a0"/>
      <stop offset="100%" stop-color="#c9a266"/>
    </linearGradient>

    <!-- ── Glass sheen across the top ── -->
    <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.40"/>
      <stop offset="55%"  stop-color="#ffffff" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>

    <!-- ── Case lid (lighter panel) ── -->
    <linearGradient id="caseTop" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.08"/>
    </linearGradient>

    <!-- ── Case body (translucent) ── -->
    <linearGradient id="caseBody" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.02"/>
    </linearGradient>

    <!-- ── Handle edge-light ── -->
    <linearGradient id="handleGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.55"/>
      <stop offset="50%"  stop-color="#ffffff" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.55"/>
    </linearGradient>

    <!-- ── Border stroke ── -->
    <linearGradient id="borderGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#ffffff" stop-opacity="0.60"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.10"/>
    </linearGradient>

    <!-- ── Soft outer glow for champagne details ── -->
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="0.9" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- ── Clip ambient glows to the rounded tile ── -->
    <clipPath id="tileClip">
      <rect x="0" y="0" width="32" height="32" rx="8" ry="8"/>
    </clipPath>
  </defs>

  <!-- ═══════════════ BASE TILE ═══════════════ -->
  <g clip-path="url(#tileClip)">
    <rect x="0" y="0" width="32" height="32" fill="url(#bgGrad)"/>

    <!-- Mint halo — top-left -->
    <circle cx="6" cy="6" r="14"
            fill="#a7f3d0" opacity="0.45"
            style="filter: blur(6px)"/>

    <!-- Champagne ember — bottom-right -->
    <circle cx="28" cy="28" r="12"
            fill="#f0d9a0" opacity="0.28"
            style="filter: blur(7px)"/>

    <!-- Teal micro-spark — top-right for freshness -->
    <circle cx="26" cy="6" r="7"
            fill="#5eead4" opacity="0.22"
            style="filter: blur(5px)"/>

    <!-- Glass sheen over the top half -->
    <rect x="0" y="0" width="32" height="18" fill="url(#sheen)"/>

    <!-- Faint diagonal sparkle -->
    <path d="M -4 14 L 36 0 L 36 6 L -4 20 Z"
          fill="#ffffff" opacity="0.07"/>
  </g>

  <!-- ═══════════════ BRIEFCASE — BODY ═══════════════ -->
  <path d="M10 10.5
           L7.5 13.5
           V23.5
           a2.2 2.2 0 0 0 2.2 2.2
           h12.6
           a2.2 2.2 0 0 0 2.2 -2.2
           V13.5
           L22 10.5 Z"
        fill="url(#caseBody)"
        stroke="url(#borderGrad)"
        stroke-width="0.9"
        stroke-linejoin="round"
        stroke-linecap="round"/>

  <!-- Top lid panel -->
  <path d="M10 10.5
           L7.5 13.5
           H24.5
           L22 10.5 Z"
        fill="url(#caseTop)"
        stroke="url(#borderGrad)"
        stroke-width="0.7"
        stroke-linejoin="round"/>

  <!-- ═══════════════ BRIEFCASE — HANDLE ═══════════════ -->
  <path d="M13 10.5
           V9.6
           a1.6 1.6 0 0 1 1.6 -1.6
           h2.8
           a1.6 1.6 0 0 1 1.6 1.6
           V10.5"
        fill="none"
        stroke="url(#handleGrad)"
        stroke-width="1.3"
        stroke-linecap="round"
        stroke-linejoin="round"/>

  <!-- ═══════════════ LID SEAM ═══════════════ -->
  <line x1="7.5" y1="13.5"
        x2="24.5" y2="13.5"
        stroke="#ffffff" stroke-opacity="0.72"
        stroke-width="0.9" stroke-linecap="round"/>

  <line x1="8.2" y1="12.9"
        x2="23.8" y2="12.9"
        stroke="#ffffff" stroke-opacity="0.22"
        stroke-width="0.6" stroke-linecap="round"/>

  <!-- ═══════════════ LOCK / CLASP ═══════════════ -->
  <rect x="14.6" y="12.6"
        width="2.8" height="1.8"
        rx="0.55" ry="0.55"
        fill="url(#champagne)"
        stroke="#ffffff" stroke-opacity="0.40"
        stroke-width="0.4"/>

  <circle cx="15.2" cy="13.3" r="0.35"
          fill="#ffffff" fill-opacity="0.9"/>

  <!-- ═══════════════ SMILE ═══════════════ -->
  <path d="M14 18.2
           a2.4 2.4 0 0 0 4 0"
        fill="none"
        stroke="url(#champagne)"
        stroke-width="1.4"
        stroke-linecap="round"
        filter="url(#glow)"/>

  <!-- ═══════════════ RIM LIGHTS ═══════════════ -->
  <path d="M2.5 8
           a6 6 0 0 1 5 -5.5"
        fill="none"
        stroke="#a7f3d0" stroke-opacity="0.60"
        stroke-width="0.9" stroke-linecap="round"/>

  <path d="M29.5 24
           a6 6 0 0 1 -5 5.5"
        fill="none"
        stroke="#f0d9a0" stroke-opacity="0.30"
        stroke-width="0.8" stroke-linecap="round"/>
</svg>
```


## `src/App.css`

```css
/* App.css — Premium Layout & UI Shell Styles
   Palette: Emerald & Champagne
   ───────────────────────────────────────────────────────────── */

/* ─── App Shell ──────────────────────────────────────────── */
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  background: var(--bg-void);
  color: var(--text-main);
}

/* Ambient aurora — emerald + champagne drift */
.app-shell::before {
  content: "";
  position: absolute;
  inset: -20%;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(38% 32% at 18% 12%, rgba(16, 185, 129, 0.24), transparent 70%),
    radial-gradient(34% 30% at 82% 6%, rgba(240, 217, 160, 0.16), transparent 70%),
    radial-gradient(46% 42% at 50% 110%, rgba(16, 185, 129, 0.20), transparent 72%);
  filter: blur(64px);
  animation: auroraDrift 28s ease-in-out infinite;
  will-change: transform;
}

/* Faint technical grid */
.app-shell::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.028) 1px, transparent 1px);
  background-size: 48px 48px;
  -webkit-mask-image: radial-gradient(72% 62% at 50% 38%, #000 0%, transparent 100%);
  mask-image: radial-gradient(72% 62% at 50% 38%, #000 0%, transparent 100%);
  opacity: 0.55;
}

@keyframes auroraDrift {
  0%, 100% { transform: translate3d(-5%, -4%, 0) scale(1); }
  50%      { transform: translate3d(5%, 4%, 0) scale(1.14); }
}

/* ─── Header ─────────────────────────────────────────────── */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  position: relative;
  z-index: 10;
  background: var(--surface-glass);
  backdrop-filter: blur(18px) saturate(180%);
  -webkit-backdrop-filter: blur(18px) saturate(180%);
  border-bottom: 1px solid var(--border-subtle);
}

.app-header::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(16, 185, 129, 0.6) 25%,
    rgba(240, 217, 160, 0.6) 60%,
    transparent 100%
  );
  background-size: 220% 100%;
  animation: hairlineFlow 7s linear infinite;
  pointer-events: none;
}

@keyframes hairlineFlow {
  0%   { background-position: 200% 0; }
  100% { background-position: -100% 0; }
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

/* ── Logo mark ── */
.header-logo {
  position: relative;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-amber);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-amber), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  overflow: hidden;
  transition:
    transform 0.5s var(--ease-premium),
    box-shadow 0.4s ease,
    border-color 0.4s ease;
}

.header-brand:hover .header-logo {
  transform: rotate(-6deg) scale(1.06);
  border-color: rgba(240, 217, 160, 0.6);
  box-shadow: 0 0 30px rgba(240, 217, 160, 0.32),
              inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.header-logo::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(255, 255, 255, 0.42) 50%,
    transparent 70%
  );
  transform: translateX(-130%);
  transition: transform 0.9s var(--ease-premium);
  pointer-events: none;
}

.header-brand:hover .header-logo::after {
  transform: translateX(130%);
}

.header-logo svg {
  display: block;
  width: 100%;
  height: 100%;
}

/* ── Brand text ── */
.header-text {
  min-width: 0;
}

.header-text h1 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.02em;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: linear-gradient(96deg, #ffffff 0%, #d1fae5 55%, var(--accent-soft) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}

.header-text p {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin: 2px 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Reset button ── */
.reset-button {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  flex: 0 0 auto;
  border-radius: var(--radius-full);
  background: var(--surface-card);
  border: 1px solid var(--border-light);
  color: var(--text-main);
  font-size: 0.85rem;
  font-weight: 500;
  overflow: hidden;
  isolation: isolate;
  transition: all 0.28s var(--ease-premium);
}

.reset-button::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: linear-gradient(
    110deg,
    transparent 25%,
    rgba(16, 185, 129, 0.22) 50%,
    transparent 75%
  );
  transform: translateX(-120%);
  transition: transform 0.7s var(--ease-premium);
}

.reset-button:hover {
  background: var(--surface-hover);
  border-color: var(--border-emerald);
  color: var(--accent-soft);
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.28),
              0 6px 18px rgba(0, 0, 0, 0.35);
  transform: translateY(-1px);
}

.reset-button:hover::before {
  transform: translateX(120%);
}

.reset-button:active {
  transform: translateY(0) scale(0.97);
}

.reset-button svg {
  width: 16px;
  height: 16px;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 0.5s var(--ease-premium);
}

.reset-button:hover svg {
  transform: rotate(-180deg);
}

/* ─── Chat Container ─────────────────────────────────────── */
.chat-window {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;

  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 28px,
    #000 calc(100% - 28px),
    transparent 100%
  );
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 28px,
    #000 calc(100% - 28px),
    transparent 100%
  );

  scrollbar-width: thin;
  scrollbar-color: rgba(16, 185, 129, 0.32) transparent;
}

.chat-window::-webkit-scrollbar {
  width: 10px;
}

.chat-window::-webkit-scrollbar-track {
  background: transparent;
}

.chat-window::-webkit-scrollbar-thumb {
  border-radius: var(--radius-full);
  border: 3px solid transparent;
  background-clip: content-box;
  background-image: linear-gradient(
    180deg,
    rgba(16, 185, 129, 0.55) 0%,
    rgba(240, 217, 160, 0.55) 100%
  );
}

.chat-window::-webkit-scrollbar-thumb:hover {
  background-image: linear-gradient(
    180deg,
    rgba(16, 185, 129, 0.95) 0%,
    rgba(240, 217, 160, 0.95) 100%
  );
}

/* ─── Message Rows & Bubbles ─────────────────────────────── */
.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  animation: riseIn 0.5s var(--ease-premium) both;
}

.message-row.from-assistant {
  align-self: flex-start;
}

.message-row.from-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

@keyframes riseIn {
  from { opacity: 0; transform: translateY(14px) scale(0.985); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Avatars ── */
.avatar {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  user-select: none;
}

.avatar.assistant {
  background: linear-gradient(135deg, var(--accent-primary), var(--amber-primary));
  color: #ffffff;
  box-shadow: var(--shadow-emerald);
  border: 1px solid var(--border-highlight);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}

.avatar.user {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.06));
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
}

/* ── Bubbles ── */
.bubble {
  position: relative;
  max-width: min(72ch, 78%);
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  background: var(--assistant-bubble);
  color: var(--text-main);
  font-size: 0.95rem;
  line-height: 1.65;
  overflow-wrap: anywhere;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s var(--ease-premium);
}

.message-row.from-assistant .bubble {
  border-top-left-radius: 4px;
}

.message-row.from-user .bubble {
  border-top-right-radius: 4px;
  border-color: var(--border-emerald);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.22) 0%, rgba(16, 185, 129, 0.08) 100%);
  box-shadow: 0 6px 22px rgba(16, 185, 129, 0.14),
              inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.bubble:hover {
  border-color: var(--border-light);
  box-shadow: 0 8px 26px rgba(0, 0, 0, 0.32),
              inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

/* ─── Typing Indicator ──────────────────────────────────── */
.bubble.typing {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 20px;
  background: var(--assistant-bubble);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  border-top-left-radius: 4px;
  overflow: hidden;
}

.bubble.typing::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 20%,
    rgba(240, 217, 160, 0.12) 50%,
    transparent 80%
  );
  background-size: 220% 100%;
  animation: typingSheen 2.6s linear infinite;
  pointer-events: none;
}

@keyframes typingSheen {
  0%   { background-position: 200% 0; }
  100% { background-position: -100% 0; }
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: pulse 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
.dot:nth-child(3) { animation-delay: 0s; }

@keyframes pulse {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
    background: var(--text-secondary);
    box-shadow: none;
  }
  40% {
    transform: scale(1.1);
    opacity: 1;
    background: var(--accent-soft);
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
  }
}

/* ─── Suggestion Pills ───────────────────────────────────── */
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 0 24px 16px;
  justify-content: center;
}

.suggestions button {
  position: relative;
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  padding: 10px 18px;
  border-radius: var(--radius-full);
  font-size: 0.85rem;
  overflow: hidden;
  isolation: isolate;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: riseIn 0.5s var(--ease-premium) both;
  transition: all 0.28s var(--ease-premium);
}

.suggestions button::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: linear-gradient(
    110deg,
    transparent 25%,
    rgba(240, 217, 160, 0.18) 50%,
    transparent 75%
  );
  transform: translateX(-120%);
  transition: transform 0.7s var(--ease-premium);
}

.suggestions button:hover {
  background: var(--surface-hover);
  border-color: var(--border-amber);
  color: var(--amber-bright);
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.38),
              0 0 18px var(--amber-glow);
}

.suggestions button:hover::before {
  transform: translateX(120%);
}

.suggestions button:active {
  transform: translateY(0) scale(0.97);
}

.suggestions button:nth-child(1) { animation-delay: 0.03s; }
.suggestions button:nth-child(2) { animation-delay: 0.08s; }
.suggestions button:nth-child(3) { animation-delay: 0.13s; }
.suggestions button:nth-child(4) { animation-delay: 0.18s; }
.suggestions button:nth-child(5) { animation-delay: 0.23s; }
.suggestions button:nth-child(6) { animation-delay: 0.28s; }

/* ─── Footer: Input + Brand ──────────────────────────────── */
.app-footer {
  position: relative;
  padding: 16px 24px 20px;
  background: var(--surface-glass);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border-top: 1px solid var(--border-subtle);
  z-index: 5;
}

.app-footer::before {
  content: "";
  position: absolute;
  top: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(16, 185, 129, 0.4) 50%,
    transparent 100%
  );
  pointer-events: none;
}

/* ── Input bar ── */
.input-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 6px 6px 18px;
  border-radius: var(--radius-full);
  background: var(--surface-card);
  border: 1px solid var(--border-light);
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.input-bar:focus-within {
  border-color: var(--border-emerald);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.14),
              0 0 22px rgba(16, 185, 129, 0.18);
}

.input-field {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 0.95rem;
  padding: 12px 0;
  outline: none;
}

.input-field::placeholder {
  color: var(--text-muted);
}

.send-button {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-deep));
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-emerald);
  transition: all 0.28s var(--ease-premium);
}

.send-button svg {
  width: 18px;
  height: 18px;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.04);
  box-shadow: 0 8px 26px rgba(16, 185, 129, 0.42);
}

.send-button:active:not(:disabled) {
  transform: translateY(0) scale(0.96);
}

.send-button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
}

/* ── Brand footer line ── */
.brand-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 12px;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.brand-footer-name {
  font-weight: 600;
  background: linear-gradient(
    92deg,
    var(--accent-primary) 0%,
    var(--accent-soft) 40%,
    var(--amber-primary) 80%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  animation: brandShimmer 5s ease-in-out infinite;
}

@keyframes brandShimmer {
  0%, 100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}

.brand-footer-link {
  position: relative;
  color: var(--text-secondary);
  transition: color 0.25s ease;
}

.brand-footer-link::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -3px;
  height: 1px;
  background: linear-gradient(90deg, var(--accent-bright), var(--amber-primary));
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.35s var(--ease-premium);
}

.brand-footer-link:hover {
  color: var(--accent-bright);
}

.brand-footer-link:hover::after {
  transform: scaleX(1);
}

/* ─── Focus States ───────────────────────────────────────── */
.reset-button:focus-visible,
.suggestions button:focus-visible,
.brand-footer-link:focus-visible,
.send-button:focus-visible,
.input-field:focus-visible {
  outline: 2px solid var(--accent-soft);
  outline-offset: 3px;
}

/* ─── Responsive ─────────────────────────────────────────── */
@media (max-width: 768px) {
  .app-header { padding: 14px 18px; }
  .chat-window { padding: 18px; gap: 16px; }
  .suggestions { padding: 0 18px 14px; }
  .app-footer { padding: 14px 18px 18px; }
  .bubble { max-width: 84%; }
}

@media (max-width: 520px) {
  .header-text p { display: none; }
  .header-logo { width: 38px; height: 38px; }
  .reset-button { padding: 8px 13px; font-size: 0.8rem; }
  .chat-window { padding: 14px; gap: 14px; }
  .bubble { max-width: 90%; font-size: 0.92rem; padding: 12px 15px; }
  .suggestions button { padding: 9px 15px; font-size: 0.8rem; }
  .brand-footer { gap: 10px; font-size: 0.72rem; }
  .input-bar { padding-left: 14px; }
  .send-button { width: 36px; height: 36px; }
}

/* ─── Reduced Motion ─────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .app-shell::before,
  .app-header::after,
  .bubble.typing::after,
  .brand-footer-name,
  .dot {
    animation: none !important;
  }

  .message-row,
  .suggestions button {
    animation-duration: 0.001s !important;
  }

  *,
  *::before,
  *::after {
    transition-duration: 0.001s !important;
    scroll-behavior: auto !important;
  }
}
```


## `src/App.jsx`

```jsx
import { useCallback, useMemo, memo } from 'react'
import ChatMessage from './components/ChatMessage.jsx'
import ChatInput from './components/ChatInput.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { useChat } from './hooks/useChat.js'
import { useScrollToBottom } from './hooks/useScrollToBottom.js'
import './App.css'

/* ── Suggested prompts ────────────────────────────────── */

const SUGGESTIONS = [
  'Recommend a laptop for coding under ₹1,20,000',
  'Best noise-cancelling headphones',
  'Which phone has the best camera?',
  'Suggest a refrigerator for a family of four',
  'What TV is best for gaming?',
]

/* ── Icon components (pure, memoised) ─────────────────── */

const ShoppingBagIcon = memo(function ShoppingBagIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 01-8 0" />
    </svg>
  )
})

const PlusIcon = memo(function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
})

const SendIcon = memo(function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
})

/* ── Suggestion strip ─────────────────────────────────── */

const SuggestionStrip = memo(function SuggestionStrip({ onSend }) {
  return (
    <div className="suggestions" role="region" aria-label="Suggested prompts">
      {SUGGESTIONS.map((suggestion) => (
        <button key={suggestion} type="button" onClick={() => onSend(suggestion)}>
          {suggestion}
        </button>
      ))}
    </div>
  )
})

/* ── Typing indicator ─────────────────────────────────── */

const TypingIndicator = memo(function TypingIndicator() {
  return (
    <div className="message-row from-assistant" aria-live="polite" aria-label="Assistant is typing">
      <div className="avatar assistant" aria-hidden="true">AI</div>
      <div className="bubble typing">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  )
})

/* ── Brand footer ─────────────────────────────────────── */

const BrandFooter = memo(function BrandFooter({ companyInfo, uniqueCities }) {
  if (!companyInfo) return null

  return (
    <div className="brand-footer">
      <span className="brand-footer-name">{companyInfo.name}</span>
      {companyInfo.website && (
        <a
          className="brand-footer-link"
          href={companyInfo.website}
          target="_blank"
          rel="noopener noreferrer"
        >
          {companyInfo.website.replace(/^https?:\/\//, '')}
        </a>
      )}
      {Array.isArray(companyInfo.stores) && companyInfo.stores.length > 0 && (
        <span className="brand-footer-stores">
          {companyInfo.stores.length} store{companyInfo.stores.length === 1 ? '' : 's'} &middot; {uniqueCities}
        </span>
      )}
    </div>
  )
})

/* ── App ──────────────────────────────────────────────── */

function App() {
  const { messages, isSending, companyInfo, sendMessage, resetChat, companyName } = useChat()

  const bottomRef = useScrollToBottom([messages, isSending])

  const handleSend = useCallback(
    (question) => sendMessage(question),
    [sendMessage],
  )

  const uniqueCities = useMemo(() => {
    if (!Array.isArray(companyInfo?.stores)) return ''
    return [...new Set(companyInfo.stores.map((s) => s.city).filter(Boolean))].join(', ')
  }, [companyInfo])

  return (
    <div className="app-shell">
      {/* Skip link for keyboard users */}
      <a href="#chat-main" className="sr-only sr-only-focusable">
        Skip to chat
      </a>

      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">
            <ShoppingBagIcon />
          </div>
          <div className="header-text">
            <h1>{companyName}</h1>
            <p>{companyInfo?.tagline || 'AI Shopping Assistant'}</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="reset-button"
            onClick={resetChat}
            aria-label="Start a new chat thread"
          >
            <PlusIcon />
            New chat
          </button>
        </div>
      </header>

      <ErrorBoundary>
        <main
          id="chat-main"
          className="chat-window"
          aria-label="Chat conversation history"
          tabIndex={0}
        >
          {messages.map((message) => (
            <ChatMessage key={message.id} {...message} />
          ))}

          {isSending && <TypingIndicator />}

          <div ref={bottomRef} />
        </main>
      </ErrorBoundary>

      {messages.length <= 1 && <SuggestionStrip onSend={handleSend} />}

      <footer className="app-footer">
        <ChatInput onSend={handleSend} disabled={isSending} SendIcon={SendIcon} />
        <BrandFooter companyInfo={companyInfo} uniqueCities={uniqueCities} />
      </footer>
    </div>
  )
}

export default App
```


## `src/App.test.jsx`

```jsx
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('./api.js', () => ({
  sendMessage: vi.fn(),
  getCompanyInfo: vi.fn().mockResolvedValue(null),
}))

import { sendMessage } from './api.js'
import App from './App.jsx'

beforeEach(() => {
  localStorage.clear()
  sendMessage.mockReset()
})

afterEach(() => {
  localStorage.clear()
})

describe('App', () => {
  it('shows the welcome message on first load', () => {
    render(<App />)
    expect(screen.getByText(/Trein shopping assistant/i)).toBeInTheDocument()
  })

  it('sends a message and renders the assistant reply', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('Here is a great phone')).toBeInTheDocument()
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
  })

  it('shows an error bubble when the backend call fails', async () => {
    sendMessage.mockRejectedValue(new Error('backend is down'))
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')

    expect(await screen.findByText(/backend is down/i)).toBeInTheDocument()
  })

  it('persists messages to localStorage and restores them on remount', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    const { unmount } = render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')
    await screen.findByText('Here is a great phone')

    unmount()

    render(<App />)
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
    expect(screen.getByText('Here is a great phone')).toBeInTheDocument()
  })

  it('clears history and starts a new thread on "New conversation"', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')
    await screen.findByText('Here is a great phone')

    await user.click(screen.getByRole('button', { name: /new conversation/i }))

    expect(screen.queryByText('recommend a phone')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(localStorage.getItem('agentic-salesman:chat-v1')).not.toContain('recommend a phone')
    })
  })
})
```


## `src/api.js`

```javascript
/**
 * API client — single fetch helper with error handling.
 *
 * Improvements:
 *  - AbortController support for cancellable requests
 *  - Retry-friendly: callers can pass an AbortSignal
 *  - Explicit typing of each endpoint for discoverability
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'
const API_KEY = import.meta.env.VITE_API_KEY

function buildHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  return headers
}

async function parseJsonSafely(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

/**
 * Centralised fetch helper.
 *
 * @param {string} endpoint  Path relative to API_BASE
 * @param {RequestInit & { signal?: AbortSignal }} [options]
 * @returns {Promise<any>}
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`

  let response
  try {
    response = await fetch(url, {
      headers: buildHeaders(),
      ...options,
    })
  } catch (err) {
    // Network failure or aborted request
    if (err.name === 'AbortError') throw err
    throw new Error('Network error — please check your connection and try again.')
  }

  const data = await parseJsonSafely(response)

  if (!response.ok) {
    const message = data?.detail || `Request failed (${response.status})`
    throw new Error(message)
  }

  return data
}

/* ── Public API ───────────────────────────────────────── */

export async function sendMessage(question, threadId, signal) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ question, thread_id: threadId }),
    signal,
  })
}

export async function getCompanyInfo(signal) {
  return request('/company', { signal })
}

export async function getCategories(signal) {
  return request('/categories', { signal })
}

export async function compareProducts(category, productNames, signal) {
  return request('/compare', {
    method: 'POST',
    body: JSON.stringify({ category, product_names: productNames }),
    signal,
  })
}
```


## `src/api.test.js`

```javascript
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sendMessage, fetchHistory, compareProducts } from './api.js'

function mockFetchOnce(status, body) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('sendMessage', () => {
  it('posts the question and thread_id, and returns the parsed response', async () => {
    mockFetchOnce(200, { answer: 'hi there', context: 'MOBILE', thread_id: 'abc', product: null })

    const result = await sendMessage('recommend a phone', 'abc')

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/chat',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: 'recommend a phone', thread_id: 'abc' }),
      })
    )
    expect(result.answer).toBe('hi there')
  })

  it('throws with the server-provided detail message on a non-2xx response', async () => {
    mockFetchOnce(500, { detail: 'boom' })
    await expect(sendMessage('hi', 'abc')).rejects.toThrow('boom')
  })

  it('throws a generic message when the error body has no detail field', async () => {
    mockFetchOnce(504, {})
    await expect(sendMessage('hi', 'abc')).rejects.toThrow('504')
  })

  it('does not send an X-API-Key header when VITE_API_KEY is unset', async () => {
    mockFetchOnce(200, { answer: 'hi', context: 'MOBILE', thread_id: 'abc' })
    await sendMessage('hi', 'abc')
    const headers = global.fetch.mock.calls[0][1].headers
    expect(headers['X-API-Key']).toBeUndefined()
  })
})

describe('fetchHistory', () => {
  it('GETs the history endpoint for the given thread id', async () => {
    mockFetchOnce(200, [{ role: 'user', content: 'hi' }])
    const result = await fetchHistory('abc')
    expect(global.fetch).toHaveBeenCalledWith('/api/history/abc', expect.any(Object))
    expect(result).toEqual([{ role: 'user', content: 'hi' }])
  })

  it('returns an empty array when the body is empty', async () => {
    mockFetchOnce(200, null)
    const result = await fetchHistory('abc')
    expect(result).toEqual([])
  })
})

describe('compareProducts', () => {
  it('posts the category and product names, and returns the comparison', async () => {
    const comparison = {
      category: 'laptop',
      products: { A: { price: 1 }, B: { price: 2 } },
      differing_fields: ['price'],
      missing: [],
    }
    mockFetchOnce(200, comparison)

    const result = await compareProducts('laptop', ['A', 'B'])

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/compare',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ category: 'laptop', product_names: ['A', 'B'] }),
      })
    )
    expect(result).toEqual(comparison)
  })

  it('throws with the server-provided detail message on a non-2xx response', async () => {
    mockFetchOnce(400, { detail: 'not enough products' })
    await expect(compareProducts('laptop', ['A'])).rejects.toThrow('not enough products')
  })
})
```


## `src/components/CandidateScores.jsx`

```jsx
import { useState, useCallback, memo } from 'react'
import { compareProducts } from '../api.js'
import ComparisonTable from './ComparisonTable.jsx'
import { formatINR } from '../utils/format.js'
import { getScorePercentage, getScoreTier } from '../utils/scores.js'

/* ── Score bar ────────────────────────────────────────── */

const ScoreBar = memo(function ScoreBar({ value }) {
  const pct = getScorePercentage(value)
  const tier = getScoreTier(pct)

  return (
    <div
      className={`score-bar score-bar-${tier}`}
      role="meter"
      aria-label={`Product match score: ${pct}%`}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span className="score-bar-tag">Match</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-bar-label">{pct}%</span>
    </div>
  )
})

/* ── Category candidates ──────────────────────────────── */

function CategoryCandidates({ category, candidates, label }) {
  const [comparison, setComparison] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [error, setError] = useState(null)

  if (!Array.isArray(candidates) || candidates.length === 0) return null

  const named = candidates.filter((c) => c?.name)
  const canCompare = named.length >= 2 && Boolean(category)

  const handleCompare = async () => {
    if (!canCompare || comparing) return
    setComparing(true)
    setError(null)

    try {
      const names = named.slice(0, 2).map((c) => c.name)
      const result = await compareProducts(category, names)
      setComparison(result)
    } catch (err) {
      console.error('[candidate-scores] comparison failed', err)
      setError(err?.message || 'Unable to compare these products right now.')
    } finally {
      setComparing(false)
    }
  }

  return (
    <div className="candidate-list" role="region" aria-label={label || 'Candidate products'}>
      {label && <div className="candidate-list-label">{label}</div>}

      <ul>
        {candidates.map((candidate, index) => {
          const score = candidate?._scores?.overall
          const price = candidate?.price
          const name = candidate?.name || 'Unknown product'

          return (
            <li key={candidate?.name ? `${candidate.name}-${index}` : index} className="candidate-row">
              <div className="candidate-product">
                <span className="candidate-name" title={name}>{name}</span>
                {price != null && (
                  <span className="candidate-price">{formatINR(price)}</span>
                )}
              </div>
              <ScoreBar value={score} />
            </li>
          )
        })}
      </ul>

      {canCompare && !comparison && (
        <button
          type="button"
          className="compare-button"
          onClick={handleCompare}
          disabled={comparing}
          aria-busy={comparing}
        >
          {comparing ? (
            <>
              <span className="spinner-icon" aria-hidden="true" /> Comparing…
            </>
          ) : (
            'Compare top matches'
          )}
        </button>
      )}

      {error && (
        <p className="compare-error" role="alert">
          {error}
        </p>
      )}

      {comparison && <ComparisonTable comparison={comparison} />}
    </div>
  )
}

/* ── Main export ──────────────────────────────────────── */

function CandidateScores({ candidates }) {
  if (!candidates || typeof candidates !== 'object') return null

  const entries = Object.entries(candidates).filter(
    ([, list]) => Array.isArray(list) && list.length > 0,
  )

  if (entries.length === 0) return null

  const totalMatches = entries.reduce((total, [, list]) => total + list.length, 0)

  return (
    <details className="candidate-scores">
      <summary>
        <span>Why these picks</span>
        <span className="candidate-count">{totalMatches} matches</span>
      </summary>

      <div className="candidate-scores-content">
        {entries.map(([category, list]) => (
          <CategoryCandidates
            key={category}
            category={category}
            candidates={list}
            label={entries.length > 1 ? category : null}
          />
        ))}
      </div>
    </details>
  )
}

export default memo(CandidateScores)
```


## `src/components/CandidateScores.test.jsx`

```jsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../api.js', () => ({
  compareProducts: vi.fn(),
}))

import { compareProducts } from '../api.js'
import CandidateScores from './CandidateScores.jsx'

describe('CandidateScores', () => {
  it('renders nothing when there are no candidates', () => {
    const { container } = render(<CandidateScores candidates={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when every category is empty', () => {
    const { container } = render(<CandidateScores candidates={{ Mobile: [] }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists each candidate with its match score', () => {
    render(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', price: 60000, _scores: { overall: 0.9 } },
            { name: 'Galaxy S', price: 65000, _scores: { overall: 0.6 } },
          ],
        }}
      />
    )
    expect(screen.getByText('Pixel 9')).toBeInTheDocument()
    expect(screen.getByText('Galaxy S')).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
  })

  it('labels each category (by its real catalog name) only when there is more than one', () => {
    // Categories are data-driven now (any string the `products` table has,
    // e.g. "Mobile", "Refrigerator", "Air Conditioner") and already arrive
    // in human-readable form straight from the catalog, so the category
    // key itself is the label -- no MOBILE/LAPTOP/HEADPHONE translation
    // table needed.
    const { rerender } = render(
      <CandidateScores candidates={{ Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByText('Mobile')).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }],
          Laptop: [{ name: 'Lenovo LOQ', _scores: { overall: 0.8 } }],
        }}
      />
    )
    expect(screen.getByText('Mobile')).toBeInTheDocument()
    expect(screen.getByText('Laptop')).toBeInTheDocument()
  })

  it('labels a brand-new catalog category (e.g. Refrigerator) the same way, with zero code changes', () => {
    render(
      <CandidateScores
        candidates={{
          Refrigerator: [{ name: 'Trein Cool 200', _scores: { overall: 0.9 } }],
          'Air Conditioner': [{ name: 'Trein Chill 1.5T', _scores: { overall: 0.7 } }],
        }}
      />
    )
    expect(screen.getByText('Refrigerator')).toBeInTheDocument()
    expect(screen.getByText('Air Conditioner')).toBeInTheDocument()
  })

  it('shows a Compare button only when a category has 2+ named candidates', () => {
    const { rerender } = render(
      <CandidateScores candidates={{ Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByRole('button', { name: /compare/i })).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )
    expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument()
  })

  it('fetches and renders a comparison when Compare is clicked, using the category as-is', async () => {
    // /api/compare takes the category exactly as the catalog has it (see
    // ENDPOINTS/endpoints.py's CompareRequest + TOOLS/product_tools.py's
    // case-insensitive lookup) -- no more translating it through a fixed
    // MOBILE -> 'phone' style map first.
    compareProducts.mockResolvedValue({
      category: 'Mobile',
      products: { 'Pixel 9': { price: 60000 }, 'Galaxy S': { price: 65000 } },
      differing_fields: ['price'],
      missing: [],
    })
    const user = userEvent.setup()
    render(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )

    await user.click(screen.getByRole('button', { name: /compare/i }))

    expect(compareProducts).toHaveBeenCalledWith('Mobile', ['Pixel 9', 'Galaxy S'])
    expect(await screen.findByText('₹60,000')).toBeInTheDocument()
  })
})
```


## `src/components/ChatInput.jsx`

```jsx
import { memo, useRef, useState, useCallback } from 'react'
import { useAutoResize } from '../hooks/useAutoResize.js'

/**
 * Chat input with auto-resizing textarea and keyboard submit.
 *
 * Improvements:
 *  - Wrapped in React.memo (pure — only re-renders when props change)
 *  - useAutoResize extracted to a reusable hook
 *  - useCallback on handlers to keep stable references
 *  - Better focus management: returns focus after send
 */
function ChatInput({ onSend, disabled = false, SendIcon }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)
  const resizeTextarea = useAutoResize(textareaRef, 120)

  const resetHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [])

  const handleSubmit = useCallback(
    (event) => {
      event.preventDefault()
      const trimmed = value.trim()
      if (!trimmed || disabled) return

      onSend(trimmed)
      setValue('')
      resetHeight()

      // Return focus to textarea after sending
      requestAnimationFrame(() => textareaRef.current?.focus())
    },
    [value, disabled, onSend, resetHeight],
  )

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        handleSubmit(event)
      }
    },
    [handleSubmit],
  )

  const handleChange = useCallback(
    (event) => {
      setValue(event.target.value)
      resizeTextarea(event)
    },
    [resizeTextarea],
  )

  const isActionDisabled = disabled || !value.trim()

  return (
    <form className="chat-input" onSubmit={handleSubmit} role="search">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? 'Assistant is thinking…' : 'Ask about any product...'}
        rows={1}
        disabled={disabled}
        aria-label="Chat message"
      />

      <button
        type="submit"
        disabled={isActionDisabled}
        aria-disabled={isActionDisabled}
        aria-label="Send message"
      >
        {SendIcon ? <SendIcon /> : 'Send'}
      </button>
    </form>
  )
}

export default memo(ChatInput)
```


## `src/components/ChatInput.test.jsx`

```jsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInput from './ChatInput.jsx'

describe('ChatInput', () => {
  it('submits the trimmed message on Enter and clears the box', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByPlaceholderText(/ask about/i)
    await user.type(textarea, '  recommend a phone  ')
    await user.keyboard('{Enter}')

    expect(onSend).toHaveBeenCalledWith('recommend a phone')
    expect(textarea).toHaveValue('')
  })

  it('does not submit on Shift+Enter (newline instead)', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByPlaceholderText(/ask about/i)
    await user.type(textarea, 'line one')
    await user.keyboard('{Shift>}{Enter}{/Shift}')

    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not submit an empty/whitespace-only message', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    await user.type(screen.getByPlaceholderText(/ask about/i), '   ')
    await user.keyboard('{Enter}')

    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables the textarea and button while disabled=true', () => {
    render(<ChatInput onSend={vi.fn()} disabled />)
    expect(screen.getByPlaceholderText(/ask about/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })
})
```


## `src/components/ChatMessage.jsx`

```jsx
import { memo, lazy, Suspense, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { hasTopPicks } from '../utils/scores.js'

// Lazy-load heavy sub-components — they contain large rule sets and tables
const TopPicksPanel = lazy(() => import('./TopPicks.jsx'))
const CandidateScores = lazy(() => import('./CandidateScores.jsx'))

/* ── Confidence badge ─────────────────────────────────── */

const CONFIDENCE_TIERS = { high: 75, medium: 50 }

function tierFor(pct) {
  if (pct >= CONFIDENCE_TIERS.high) return 'high'
  if (pct >= CONFIDENCE_TIERS.medium) return 'medium'
  return 'low'
}

const ConfidenceBadge = memo(function ConfidenceBadge({ confidence }) {
  if (confidence == null) return null

  const pct = Math.round(Math.max(0, Math.min(1, Number(confidence))) * 100)
  const tier = tierFor(pct)

  return (
    <div
      className={`confidence-badge confidence-${tier}`}
      title="Evaluator match confidence level"
      aria-label={`Confidence level: ${pct}%`}
    >
      Confidence: {pct}%
    </div>
  )
})

/* ── Recommendation content ───────────────────────────── */

function RecommendationContent({ confidence, content, product, candidates, showTopPicks }) {
  return (
    <Suspense fallback={<p className="loading-text">Loading details…</p>}>
      <ConfidenceBadge confidence={confidence} />
      {!showTopPicks && content && <ReactMarkdown>{content}</ReactMarkdown>}
      <TopPicksPanel product={product} />
      <CandidateScores candidates={candidates} />
    </Suspense>
  )
}

/* ── Chat message ─────────────────────────────────────── */

function ChatMessage({
  role,
  content,
  isError = false,
  response_type,
  product,
  candidates,
  confidence,
}) {
  const isUser = role === 'user'
  const isRecommendation = !isUser && response_type === 'recommendation' && !isError
  const showTopPicks = isRecommendation && hasTopPicks(product)

  const bubbleClass = `bubble${isError ? ' error' : ''}`

  // Descriptive label for screen readers
  const ariaLabel = useMemo(() => {
    if (isUser) return 'Your message'
    if (isError) return 'Error message'
    return 'Assistant response'
  }, [isUser, isError])

  return (
    <div
      className={`message-row ${isUser ? 'from-user' : 'from-assistant'}`}
      role="article"
      aria-label={ariaLabel}
    >
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`} aria-hidden="true">
        {isUser ? 'You' : 'AI'}
      </div>

      <div className={bubbleClass}>
        {isUser ? (
          <p>{content}</p>
        ) : isRecommendation ? (
          <RecommendationContent
            confidence={confidence}
            content={content}
            product={product}
            candidates={candidates}
            showTopPicks={showTopPicks}
          />
        ) : (
          <ReactMarkdown>
            {content || (isError ? 'Something went wrong.' : '')}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}

export default memo(ChatMessage)
```


## `src/components/ChatMessage.test.jsx`

```jsx
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatMessage from './ChatMessage.jsx'

function pick(overrides = {}) {
  return {
    rank: 1,
    name: 'iPhone 14',
    specs: { brand: 'Apple' },
    scores: { overall: 0.9 },
    buy: {
      price: 60000,
      currency: 'INR',
      mrp: null,
      discount_percentage: null,
      units_available: null,
      in_stock: null,
      online_link: 'https://example.com',
      offline_availability: null,
    },
    why_this: 'Great value',
    key_features: ['A15 chip'],
    why_suits_you: 'Fits your budget',
    ...overrides,
  }
}

describe('ChatMessage', () => {
  it('renders a user message as plain text', () => {
    render(<ChatMessage role="user" content="recommend a phone" />)
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
  })

  it('renders an assistant message as Markdown', () => {
    render(<ChatMessage role="assistant" content="# Recommended Phone" />)
    expect(screen.getByRole('heading', { name: 'Recommended Phone' })).toBeInTheDocument()
  })

  it('applies the error style and does not render top-pick cards for error messages', () => {
    const { container } = render(
      <ChatMessage
        role="assistant"
        content="Something went wrong"
        isError
        product={{ top_picks: [pick()] }}
      />
    )
    expect(container.querySelector('.bubble.error')).toBeInTheDocument()
    expect(container.querySelector('.top-pick')).not.toBeInTheDocument()
  })

  it('renders the why-this / key-features / buy-now cards for a single-category product', () => {
    render(
      <ChatMessage role="assistant" content="Here you go" product={{ top_picks: [pick()] }} />
    )
    expect(screen.getByText('iPhone 14')).toBeInTheDocument()
    expect(screen.getByText('Great value')).toBeInTheDocument()
    expect(screen.getByText('Fits your budget')).toBeInTheDocument()
    expect(screen.getByText('A15 chip')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /buy online/i })).toHaveAttribute(
      'href',
      'https://example.com'
    )
  })

  it('renders one set of cards per category for a multi-category product', () => {
    render(
      <ChatMessage
        role="assistant"
        content="Here you go"
        product={{
          MOBILE: { top_picks: [pick({ name: 'iPhone 14' })] },
          HEADPHONE: { top_picks: [pick({ name: 'SoundMax 200', why_this: 'Great sound' })] },
        }}
      />
    )
    expect(screen.getByText('iPhone 14')).toBeInTheDocument()
    expect(screen.getByText('SoundMax 200')).toBeInTheDocument()
  })

  it('renders nothing extra when product is null', () => {
    const { container } = render(<ChatMessage role="assistant" content="hi" product={null} />)
    expect(container.querySelector('.top-pick')).not.toBeInTheDocument()
  })

  it('renders a confidence badge when confidence is present', () => {
    render(<ChatMessage role="assistant" content="hi" confidence={0.82} />)
    expect(screen.getByText('Confidence: 82%')).toBeInTheDocument()
  })

  it('renders no confidence badge when confidence is null', () => {
    render(<ChatMessage role="assistant" content="hi" confidence={null} />)
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('does not render a confidence badge for user messages even if confidence is set', () => {
    render(<ChatMessage role="user" content="hi" confidence={0.82} />)
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('renders the candidate scores disclosure when candidates are present', () => {
    render(
      <ChatMessage
        role="assistant"
        content="hi"
        candidates={{ MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }}
      />
    )
    expect(screen.getByText('Why these picks')).toBeInTheDocument()
  })
})
```


## `src/components/ComparisonTable.jsx`

```jsx
import { memo, useMemo } from 'react'
import { formatSpecValue } from '../utils/format.js'

/* ── Data extraction helpers ──────────────────────────── */

function extractProducts(comparison) {
  if (!comparison) return []
  if (Array.isArray(comparison)) return comparison
  if (Array.isArray(comparison.products)) return comparison.products
  if (Array.isArray(comparison.comparison)) return comparison.comparison
  if (Array.isArray(comparison.items)) return comparison.items
  return []
}

function getSpecs(product) {
  return product?.specs || product?.features || {}
}

function getProductId(product, index) {
  return product.id || product.product_id || product.asin || product.name || index
}

/* ── Component ────────────────────────────────────────── */

function ComparisonTable({ comparison, products: productsProp, selectedProductId }) {
  const products = productsProp ?? extractProducts(comparison)

  // Collect every spec key across all products, preserving first-seen order.
  const specKeys = useMemo(() => {
    const keys = []
    products.forEach((product) => {
      Object.keys(getSpecs(product)).forEach((key) => {
        if (!keys.includes(key)) keys.push(key)
      })
    })
    return keys
  }, [products])

  if (products.length === 0 || specKeys.length === 0) return null

  return (
    <div className="comparison-table-wrap" role="region" aria-label="Product comparison">
      <table
        className="comparison-table"
        role="table"
        aria-label="Product feature comparison matrix"
      >
        <thead>
          <tr>
            <th scope="col">Product</th>
            {specKeys.map((key) => (
              <th scope="col" key={key}>
                {key.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {products.map((product, index) => {
            const productId = getProductId(product, index)
            const isSelected =
              selectedProductId != null && String(productId) === String(selectedProductId)
            const specs = getSpecs(product)
            const productName = product.name || 'Unknown product'

            return (
              <tr key={productId} className={isSelected ? 'selected-row' : undefined}>
                <th scope="row">
                  <div className="product-cell">
                    <span className="product-link" title={productName}>
                      {productName}
                    </span>
                    {product.store && (
                      <span className="product-store">{product.store}</span>
                    )}
                  </div>
                </th>

                {specKeys.map((key) => (
                  <td key={key}>{formatSpecValue(specs[key])}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default memo(ComparisonTable)
```


## `src/components/ComparisonTable.test.jsx`

```jsx
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComparisonTable from './ComparisonTable.jsx'

describe('ComparisonTable', () => {
  it('renders nothing when there is no comparison', () => {
    const { container } = render(<ComparisonTable comparison={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for a single product', () => {
    const { container } = render(
      <ComparisonTable comparison={{ products: { A: { price: 1 } }, differing_fields: [] }} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders one row per field and one column per product', () => {
    render(
      <ComparisonTable
        comparison={{
          category: 'laptop',
          products: {
            'Lenovo LOQ': { price: 72999, ram: '16GB' },
            'HP Pavilion': { price: 55000, ram: '8GB' },
          },
          differing_fields: ['price', 'ram'],
          missing: [],
        }}
      />
    )
    expect(screen.getByText('Lenovo LOQ')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion')).toBeInTheDocument()
    expect(screen.getByText('₹72,999')).toBeInTheDocument()
    expect(screen.getByText('₹55,000')).toBeInTheDocument()
  })

  it('hides the internal id field and gives friendly labels', () => {
    render(
      <ComparisonTable
        comparison={{
          products: {
            A: { price: 1000, brand: 'Acme' },
            B: { price: 2000, brand: 'Zeta' },
          },
          differing_fields: ['price', 'brand'],
          missing: [],
        }}
      />
    )
    expect(screen.getByText('Price')).toBeInTheDocument()
    expect(screen.getByText('Brand')).toBeInTheDocument()
    expect(screen.queryByText('id')).not.toBeInTheDocument()
  })

  it('marks differing fields', () => {
    const { container } = render(
      <ComparisonTable
        comparison={{
          products: { A: { price: 1 }, B: { price: 2 } },
          differing_fields: ['price'],
          missing: [],
        }}
      />
    )
    expect(container.querySelector('tr.differs')).toBeInTheDocument()
  })
})
```


## `src/components/Errorboundary.jsx`

```jsx
import { Component } from 'react'

/**
 * Catches render errors in any child tree and shows a recovery UI
 * instead of a blank screen.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Uncaught render error:', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      // Allow a custom fallback via props
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div role="alert" className="error-boundary">
          <h2 className="error-boundary-title">Something went wrong</h2>
          <p className="error-boundary-message">
            An unexpected error occurred. You can try resetting the view below.
          </p>
          {this.state.error?.message && (
            <pre className="error-boundary-details">{this.state.error.message}</pre>
          )}
          <button
            type="button"
            className="error-boundary-button"
            onClick={this.handleReset}
          >
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
```


## `src/components/Logo.jsx`

```jsx
import { memo } from 'react'

/**
 * Inline SVG logo with emerald/champagne gradient.
 * Pure presentational — wrapped in React.memo.
 */
function Logo({ size = 42 }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      role="img"
      aria-label="Chat logo"
    >
      <defs>
        <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6ee7b7" />
          <stop offset="45%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#065f46" />
        </linearGradient>

        <linearGradient id="champagne" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fff5db" />
          <stop offset="55%" stopColor="#f0d9a0" />
          <stop offset="100%" stopColor="#c9a266" />
        </linearGradient>

        <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.40" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>

        <linearGradient id="caseTop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.26" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.08" />
        </linearGradient>

        <linearGradient id="caseBody" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.02" />
        </linearGradient>

        <linearGradient id="handleGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.55" />
        </linearGradient>

        <linearGradient id="borderGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.60" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.10" />
        </linearGradient>

        <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="0.9" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <clipPath id="tileClip">
          <rect x="0" y="0" width="32" height="32" rx="8" ry="8" />
        </clipPath>
      </defs>

      <g clipPath="url(#tileClip)">
        <rect x="0" y="0" width="32" height="32" fill="url(#bgGrad)" />
        <circle cx="6" cy="6" r="14" fill="#a7f3d0" opacity="0.45" style={{ filter: 'blur(6px)' }} />
        <circle cx="28" cy="28" r="12" fill="#f0d9a0" opacity="0.28" style={{ filter: 'blur(7px)' }} />
        <circle cx="26" cy="6" r="7" fill="#5eead4" opacity="0.22" style={{ filter: 'blur(5px)' }} />
        <rect x="0" y="0" width="32" height="18" fill="url(#sheen)" />
        <path d="M -4 14 L 36 0 L 36 6 L -4 20 Z" fill="#ffffff" opacity="0.07" />
      </g>

      <path
        d="M10 10.5 L7.5 13.5 V23.5 a2.2 2.2 0 0 0 2.2 2.2 h12.6 a2.2 2.2 0 0 0 2.2 -2.2 V13.5 L22 10.5 Z"
        fill="url(#caseBody)" stroke="url(#borderGrad)"
        strokeWidth="0.9" strokeLinejoin="round" strokeLinecap="round"
      />

      <path
        d="M10 10.5 L7.5 13.5 H24.5 L22 10.5 Z"
        fill="url(#caseTop)" stroke="url(#borderGrad)"
        strokeWidth="0.7" strokeLinejoin="round"
      />

      <path
        d="M13 10.5 V9.6 a1.6 1.6 0 0 1 1.6 -1.6 h2.8 a1.6 1.6 0 0 1 1.6 1.6 V10.5"
        fill="none" stroke="url(#handleGrad)"
        strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"
      />

      <line x1="7.5" y1="13.5" x2="24.5" y2="13.5" stroke="#ffffff" strokeOpacity="0.72" strokeWidth="0.9" strokeLinecap="round" />
      <line x1="8.2" y1="12.9" x2="23.8" y2="12.9" stroke="#ffffff" strokeOpacity="0.22" strokeWidth="0.6" strokeLinecap="round" />

      <rect x="14.6" y="12.6" width="2.8" height="1.8" rx="0.55" ry="0.55" fill="url(#champagne)" stroke="#ffffff" strokeOpacity="0.40" strokeWidth="0.4" />
      <circle cx="15.2" cy="13.3" r="0.35" fill="#ffffff" fillOpacity="0.9" />

      <path
        d="M14 18.2 a2.4 2.4 0 0 0 4 0"
        fill="none" stroke="url(#champagne)"
        strokeWidth="1.4" strokeLinecap="round" filter="url(#glow)"
      />

      <path d="M2.5 8 a6 6 0 0 1 5 -5.5" fill="none" stroke="#a7f3d0" strokeOpacity="0.60" strokeWidth="0.9" strokeLinecap="round" />
      <path d="M29.5 24 a6 6 0 0 1 -5 5.5" fill="none" stroke="#f0d9a0" strokeOpacity="0.30" strokeWidth="0.8" strokeLinecap="round" />
    </svg>
  )
}

export default memo(Logo)
```


## `src/components/TopPicks.jsx`

```jsx
import { useState, useEffect, useCallback, memo, useMemo } from 'react'
import { formatINR, parseSpecNumber, splitSentences, mapsSearchUrl } from '../utils/format.js'
import { isTopPicksShape } from '../utils/scores.js'
import { SPEC_LABELS, evaluateSpec } from '../utils/specRules.js'

/* ─────────────────────────────────────────────────────────
   Product selector (tab-like switcher)
   ───────────────────────────────────────────────────────── */

const ProductSelector = memo(function ProductSelector({ picks, selectedRank, onSelect }) {
  // Generate a unique id prefix for ARIA tab/tabpanel pairing
  const panelId = 'picks-panel'

  return (
    <div className="product-selector" role="tablist" aria-label="Top picks options">
      {picks.map((pick, index) => {
        const isSelected = pick.rank === selectedRank
        return (
          <button
            type="button"
            key={pick.rank ?? pick.name}
            className={`product-option${isSelected ? ' active' : ''}`}
            onClick={() => onSelect(pick.rank)}
            role="tab"
            id={`tab-${pick.rank}`}
            aria-selected={isSelected}
            aria-controls={panelId}
            tabIndex={isSelected ? 0 : -1}
          >
            <div className="option-number">{String(index + 1).padStart(2, '0')}</div>
            <div className="option-name">{pick.name || 'Unknown product'}</div>
            <div className="option-price">{formatINR(pick.buy?.price) ?? 'Price unavailable'}</div>
            {pick.rank === 1 && <div className="option-status">Recommended</div>}
          </button>
        )
      })}
    </div>
  )
})

/* ─────────────────────────────────────────────────────────
   Hero section for the selected pick
   ───────────────────────────────────────────────────────── */

const RecommendedHero = memo(function RecommendedHero({ pick }) {
  const { price, mrp, discount_percentage: discount } = pick.buy || {}
  return (
    <section className="recommended" aria-label="Selected product details">
      <div className="recommended-top">
        <div>
          <span className="recommended-label">Selected product</span>
          <h2 className="product-title">{pick.name || 'Unknown product'}</h2>
        </div>
        <div className="product-price">
          <div className="price">{formatINR(price) ?? 'Price unavailable'}</div>
          {mrp != null && price != null && mrp > price && (
            <div className="mrp">
              <del>{formatINR(mrp)}</del>
            </div>
          )}
          {discount != null && <div className="discount">{discount}% OFF</div>}
        </div>
      </div>
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   "Why this" + specs grid
   ───────────────────────────────────────────────────────── */

const WhyAndFeatures = memo(function WhyAndFeatures({ pick }) {
  const specEntries = useMemo(
    () => Object.entries(pick.specs || {}).filter(([, v]) => v != null && v !== ''),
    [pick.specs],
  )

  return (
    <div className="info-grid">
      <section className="card">
        <h3 className="card-title">
          Why this {pick.name ? pick.name.split(' ')[0] : 'product'}?
        </h3>
        <p className="card-description">
          {pick.why_this || 'No verified reasoning available yet.'}
        </p>
      </section>

      <section className="card">
        <h3 className="card-title">Specifications</h3>
        {specEntries.length > 0 ? (
          <div className="spec-detail-grid" role="list">
            {specEntries.map(([key, value]) => {
              const { quality, tip } = evaluateSpec(key, value)
              return (
                <div
                  className={`spec-detail-row spec-${quality}`}
                  key={key}
                  title={tip || undefined}
                  role="listitem"
                >
                  <span className="spec-detail-label">{SPEC_LABELS[key] || key}</span>
                  <span className="spec-detail-value">
                    {quality === 'good' && <span className="spec-indicator good" aria-label="Good">✓</span>}
                    {quality === 'bad' && <span className="spec-indicator bad" aria-label="Weak">✗</span>}
                    {String(value)}
                  </span>
                  {tip && <span className="spec-detail-tip">{tip}</span>}
                </div>
              )
            })}
          </div>
        ) : (
          <p className="card-description">No verified specs listed yet.</p>
        )}
      </section>
    </div>
  )
})

/* ─────────────────────────────────────────────────────────
   "Why this suits you" section
   ───────────────────────────────────────────────────────── */

const SuitsYou = memo(function SuitsYou({ pick }) {
  const items = useMemo(() => splitSentences(pick.why_suits_you), [pick.why_suits_you])

  if (items.length === 0) return null

  return (
    <section className="card suits">
      <h3 className="card-title">Why this suits you</h3>
      {items.length === 1 ? (
        <p className="card-description">{items[0]}</p>
      ) : (
        <div className="suit-grid">
          {items.map((item, index) => (
            <div className="suit" key={index}>
              <span className="suit-number">{String(index + 1).padStart(2, '0')}</span>
              {item}
            </div>
          ))}
        </div>
      )}
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Buy card with online/offline links
   ───────────────────────────────────────────────────────── */

const BuyCard = memo(function BuyCard({ pick }) {
  const buy = pick.buy || {}
  const {
    price,
    mrp,
    units_available: units,
    in_stock: inStock,
    online_link: onlineLink,
    offline_availability: offline,
  } = buy
  const save = mrp != null && price != null && mrp > price ? mrp - price : null

  const availabilityParts = useMemo(() => {
    const parts = []
    if (units != null) parts.push(`${units} unit${units === 1 ? '' : 's'} available`)
    else if (inStock != null) parts.push(inStock ? 'In stock' : 'Out of stock')
    if (offline) parts.push(offline)
    return parts
  }, [units, inStock, offline])

  const showroomQuery =
    offline && offline.toLowerCase() !== 'not available in offline stores' && pick.specs?.brand
      ? `${pick.specs.brand} showroom near me`
      : null

  return (
    <section className="buy" aria-label={`Buy ${pick.name || 'product'}`}>
      <div>
        <h3 className="buy-title">Buy this {pick.name || 'product'}</h3>
        <p className="buy-description">
          {pick.rank === 1
            ? 'Top recommended match based on your requirements.'
            : 'A strong alternative worth considering.'}
        </p>
        <div className="buy-details">
          <span className="buy-price">{formatINR(price) ?? 'Price unavailable'}</span>
          {mrp != null && price != null && mrp > price && (
            <span className="mrp"><del>{formatINR(mrp)}</del></span>
          )}
          {save != null && <span className="save">Save {formatINR(save)}</span>}
        </div>
        {availabilityParts.length > 0 && (
          <div className="availability">{availabilityParts.join(' · ')}</div>
        )}
      </div>
      <div className="buy-actions">
        {onlineLink ? (
          <a className="buy-button" href={onlineLink} target="_blank" rel="noopener noreferrer">
            Buy online
          </a>
        ) : (
          <span className="buy-button disabled" aria-disabled="true">
            Online link not available
          </span>
        )}
        {showroomQuery && (
          <a
            className="showroom-button"
            href={mapsSearchUrl(showroomQuery)}
            target="_blank"
            rel="noopener noreferrer"
          >
            See nearby offline showroom
          </a>
        )}
      </div>
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Side-by-side comparison table
   ───────────────────────────────────────────────────────── */

const COMPARISON_ROWS = [
  { key: 'price', label: 'Price', direction: 'lower', get: (p) => p.buy?.price, format: formatINR },
  { key: 'discount', label: 'Discount', direction: 'higher', get: (p) => p.buy?.discount_percentage ?? null, format: (v) => `${v}%` },
  { key: 'ram', label: 'RAM', direction: 'higher', get: (p) => parseSpecNumber(p.specs?.ram), display: (p) => p.specs?.ram },
  { key: 'storage', label: 'Storage', direction: 'higher', get: (p) => parseSpecNumber(p.specs?.storage), display: (p) => p.specs?.storage },
  { key: 'brand', label: 'Brand', direction: null, get: () => null, display: (p) => p.specs?.brand },
  { key: 'processor', label: 'Processor', direction: null, get: () => null, display: (p) => p.specs?.processor || p.specs?.type },
  { key: 'color', label: 'Color', direction: null, get: () => null, display: (p) => p.specs?.color },
]

const ComparisonSection = memo(function ComparisonSection({ picks, selectedRank, onSelect }) {
  if (!Array.isArray(picks) || picks.length < 2) return null

  const rows = COMPARISON_ROWS.filter((row) =>
    picks.some((pick) => (row.display ? row.display(pick) : row.get(pick)) != null),
  )
  if (rows.length === 0) return null

  const bestWorstByRow = {}
  rows.forEach((row) => {
    if (!row.direction) return
    const known = picks.map((p) => row.get(p)).filter((v) => v != null)
    if (known.length < 2) return
    const best = row.direction === 'lower' ? Math.min(...known) : Math.max(...known)
    const worst = row.direction === 'lower' ? Math.max(...known) : Math.min(...known)
    bestWorstByRow[row.key] = best === worst ? null : { best, worst }
  })

  return (
    <section aria-label="Product comparison">
      <div className="comparison-header">
        <h2>Compare top {picks.length} picks</h2>
        <p>Click a product to view its complete details above.</p>
      </div>
      <div className="comparison" role="region" aria-label="Comparison table">
        <table>
          <caption className="sr-only">Side-by-side comparison of the top {picks.length} picks</caption>
          <thead>
            <tr>
              <th scope="col">Product</th>
              {rows.map((row) => (
                <th scope="col" key={row.key}>{row.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {picks.map((pick) => (
              <tr key={pick.rank} className={pick.rank === selectedRank ? 'selected-row' : undefined}>
                <td>
                  <div className="product-cell">
                    <button type="button" className="product-link" onClick={() => onSelect(pick.rank)}>
                      {pick.name ?? `Pick ${pick.rank}`}
                    </button>
                    <span className="product-store">Click to view details</span>
                  </div>
                </td>
                {rows.map((row) => {
                  const numericValue = row.direction ? row.get(pick) : null
                  const raw = row.display ? row.display(pick) : row.get(pick)
                  const shown = row.format && numericValue != null ? row.format(numericValue) : raw ?? '—'
                  const bw = bestWorstByRow[row.key]

                  let cellClass = ''
                  if (bw && numericValue != null) {
                    if (numericValue === bw.best) cellClass = 'spec-best'
                    else if (numericValue === bw.worst) cellClass = 'spec-worse'
                  }

                  return <td key={row.key} className={cellClass || undefined}>{shown}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="comparison-legend" aria-hidden="true">
        <div className="legend-item"><span className="legend-box legend-best" /> Best specification</div>
        <div className="legend-item"><span className="legend-box legend-worse" /> Weaker specification</div>
      </div>
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Category top picks (one category with its N products)
   ───────────────────────────────────────────────────────── */

function CategoryTopPicks({ picks, label, idPrefix }) {
  const [selectedRank, setSelectedRank] = useState(picks?.[0]?.rank ?? 1)

  // Sync selection when picks data changes
  useEffect(() => {
    if (Array.isArray(picks) && picks.length > 0) {
      if (!picks.some((p) => p.rank === selectedRank)) {
        setSelectedRank(picks[0].rank)
      }
    }
  }, [picks, selectedRank])

  const handleSelect = useCallback((rank) => setSelectedRank(rank), [])

  if (!Array.isArray(picks) || picks.length === 0) return null

  const selectedPick = picks.find((p) => p.rank === selectedRank) || picks[0]

  return (
    <section
      className="top-picks"
      id={`picks-${idPrefix}`}
      role="tabpanel"
      aria-label={label || 'Top picks'}
    >
      {label && <div className="top-picks-label">{label}</div>}

      {picks.length > 1 && (
        <ProductSelector picks={picks} selectedRank={selectedPick.rank} onSelect={handleSelect} />
      )}

      <RecommendedHero pick={selectedPick} />
      <WhyAndFeatures pick={selectedPick} />
      <SuitsYou pick={selectedPick} />
      <BuyCard pick={selectedPick} />
      <ComparisonSection picks={picks} selectedRank={selectedPick.rank} onSelect={handleSelect} />
    </section>
  )
}

/* ─────────────────────────────────────────────────────────
   Main panel — dispatches to single or multi-category
   ───────────────────────────────────────────────────────── */

function TopPicksPanel({ product }) {
  if (!product || typeof product !== 'object') return null

  if (isTopPicksShape(product)) {
    return <CategoryTopPicks picks={product.top_picks} idPrefix="single" />
  }

  const entries = Object.entries(product).filter(([, value]) => isTopPicksShape(value))
  if (entries.length === 0) return null

  return (
    <div className="top-picks-group">
      {entries.map(([category, value]) => (
        <CategoryTopPicks
          key={category}
          picks={value.top_picks}
          label={category}
          idPrefix={category}
        />
      ))}
    </div>
  )
}

export default memo(TopPicksPanel)
```


## `src/components/TopPicks.test.jsx`

```jsx
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TopPicksPanel from './TopPicks.jsx'

function pick(overrides = {}) {
  return {
    rank: 1,
    name: 'HP Pavilion 15',
    specs: { brand: 'HP', ram: '16GB', storage: '512GB', processor: 'Ryzen 7' },
    scores: { overall: 0.9 },
    buy: {
      price: 69990,
      currency: 'INR',
      mrp: null,
      discount_percentage: null,
      units_available: null,
      in_stock: null,
      online_link: null,
      offline_availability: null,
    },
    why_this: 'Great performance for the price.',
    key_features: ['Ryzen 7', '16GB RAM'],
    why_suits_you: 'Matches your budget and use case.',
    ...overrides,
  }
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

describe('TopPicksPanel', () => {
  it('renders nothing when product is null', () => {
    const { container } = render(<TopPicksPanel product={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when there is no top_picks shape anywhere in product', () => {
    const { container } = render(<TopPicksPanel product={{ foo: 'bar' }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the why-this, key-features, why-suits-you and buy-now cards for a pick', () => {
    render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion 15')).toBeInTheDocument()
    expect(screen.getByText('Why this HP Pavilion 15?')).toBeInTheDocument()
    expect(screen.getByText('Great performance for the price.')).toBeInTheDocument()
    expect(screen.getByText('Why this suits you')).toBeInTheDocument()
    expect(screen.getByText('Matches your budget and use case.')).toBeInTheDocument()
    expect(screen.getByText('Ryzen 7')).toBeInTheDocument()
    expect(screen.getByText('16GB RAM')).toBeInTheDocument()
    expect(screen.getByText('₹69,990')).toBeInTheDocument()
  })

  it('shows a discount badge and struck-through MRP when the catalog has one', () => {
    render(
      <TopPicksPanel
        product={{ top_picks: [pick({ buy: { ...pick().buy, price: 69990, mrp: 99990, discount_percentage: 30 } })] }}
      />
    )
    expect(screen.getByText('₹99,990')).toBeInTheDocument()
    expect(screen.getByText('30% off')).toBeInTheDocument()
  })

  it('falls back to "Not available"/"Not tracked" when the catalog does not track a buy field', () => {
    render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    // "Not tracked" appears twice: units available, and stock status.
    expect(screen.getAllByText('Not tracked')).toHaveLength(2)
    expect(screen.getByText('Not available')).toBeInTheDocument() // offline availability
    expect(screen.getByText('Online link not available')).toBeInTheDocument()
  })

  it('shows an in-stock / out-of-stock badge based on buy.in_stock', () => {
    const { rerender } = render(
      <TopPicksPanel product={{ top_picks: [pick({ buy: { ...pick().buy, in_stock: true, units_available: 4 } })] }} />
    )
    expect(screen.getByText('In stock')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()

    rerender(
      <TopPicksPanel product={{ top_picks: [pick({ buy: { ...pick().buy, in_stock: false, units_available: 0 } })] }} />
    )
    expect(screen.getByText('Out of stock')).toBeInTheDocument()
  })

  it('links the online store when the catalog has a link', () => {
    render(
      <TopPicksPanel
        product={{ top_picks: [pick({ buy: { ...pick().buy, online_link: 'https://shop.example.com/x' } })] }}
      />
    )
    expect(screen.getByRole('link', { name: /buy online/i })).toHaveAttribute(
      'href',
      'https://shop.example.com/x'
    )
  })

  it('does not render a comparison table for a single pick', () => {
    const { container } = render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    expect(container.querySelector('.top-picks-comparison')).not.toBeInTheDocument()
  })

  it('renders a comparison table for all picks with the best value green and worst red', () => {
    const cheaperMoreRam = pick({
      rank: 1,
      name: 'Cheap & Powerful',
      specs: { ram: '16GB', storage: '512GB' },
      buy: { ...pick().buy, price: 50000 },
    })
    const pricierLessRam = pick({
      rank: 2,
      name: 'Pricier & Weaker',
      specs: { ram: '8GB', storage: '256GB' },
      buy: { ...pick().buy, price: 80000 },
    })
    const { container } = render(
      <TopPicksPanel product={{ top_picks: [cheaperMoreRam, pricierLessRam] }} />
    )

    const table = container.querySelector('.top-picks-comparison')
    expect(table).toBeInTheDocument()
    expect(within(table).getByText('Cheap & Powerful')).toBeInTheDocument()
    expect(within(table).getByText('Pricier & Weaker')).toBeInTheDocument()

    const bestCells = container.querySelectorAll('.best-cell')
    const worstCells = container.querySelectorAll('.worst-cell')
    expect(bestCells.length).toBeGreaterThan(0)
    expect(worstCells.length).toBeGreaterThan(0)

    // Price: 50000 is lower (better) so it should be a best-cell, not worst.
    const priceRow = screen.getByText('Price').closest('tr')
    expect(priceRow.querySelector('.best-cell')).toHaveTextContent('₹50,000')
    expect(priceRow.querySelector('.worst-cell')).toHaveTextContent('₹80,000')
  })

  it('scrolls to a pick\'s own cards when its comparison header is clicked', async () => {
    const user = userEvent.setup()
    const picks = [pick({ rank: 1, name: 'A' }), pick({ rank: 2, name: 'B' })]
    render(<TopPicksPanel product={{ top_picks: picks }} />)

    await user.click(screen.getByRole('button', { name: 'A' }))
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('renders one labeled section per category for a multi-category product', () => {
    render(
      <TopPicksPanel
        product={{
          Mobile: { top_picks: [pick({ name: 'Pixel 9' })] },
          Laptop: { top_picks: [pick({ name: 'HP Pavilion 15' })] },
        }}
      />
    )
    expect(screen.getByText('Mobile')).toBeInTheDocument()
    expect(screen.getByText('Laptop')).toBeInTheDocument()
    expect(screen.getByText('Pixel 9')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion 15')).toBeInTheDocument()
  })

  it('renders a brand-new catalog category (e.g. Refrigerator) the same way', () => {
    // No CATEGORY_LABELS entry needed for a category the code has never
    // heard of -- it renders using its own catalog name as the label.
    render(
      <TopPicksPanel
        product={{
          Refrigerator: { top_picks: [pick({ name: 'Trein Cool 200' })] },
          'Air Conditioner': { top_picks: [pick({ name: 'Trein Chill 1.5T' })] },
        }}
      />
    )
    expect(screen.getByText('Refrigerator')).toBeInTheDocument()
    expect(screen.getByText('Air Conditioner')).toBeInTheDocument()
  })
})
```


## `src/hooks/useAutoResize.js`

```javascript
import { useCallback } from 'react'

/**
 * Returns an onChange handler that auto-resizes a <textarea> up to `maxHeight`.
 *
 * Usage:
 *   const handleChange = useAutoResize(textareaRef, 120)
 *   <textarea ref={textareaRef} onChange={handleChange} />
 *
 * @param {React.RefObject<HTMLTextAreaElement>} ref
 * @param {number} maxHeight  Maximum pixel height before scrolling kicks in
 * @returns {(e: React.ChangeEvent<HTMLTextAreaElement>) => void}
 */
export function useAutoResize(ref, maxHeight = 120) {
  return useCallback(
    (event) => {
      const el = ref.current ?? event.target
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    },
    [ref, maxHeight],
  )
}
```


## `src/hooks/useChat.js`

```javascript
import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage as apiSendMessage, getCompanyInfo } from '../api.js'
import { useLocalStorage } from './useLocalStorage.js'

const STORAGE_KEY = 'agentic-salesman:chat-v1'
const DEFAULT_COMPANY_NAME = 'Trein'

function createThreadId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `thread-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function buildWelcomeMessage(companyName) {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      `Welcome to **${companyName}**! I'm your AI shopping assistant. Tell me what you're looking for — ` +
      "**mobiles**, **laptops**, **TVs**, **appliances** and more — and I'll find the perfect match for you.",
  }
}

/**
 * Encapsulates all chat state: messages, thread id, company info,
 * sending status, and localStorage persistence.
 */
export function useChat() {
  const [stored, setStored, clearStored] = useLocalStorage(STORAGE_KEY, null)

  const [messages, setMessages] = useState(() =>
    stored?.messages ?? [buildWelcomeMessage(DEFAULT_COMPANY_NAME)],
  )
  const [threadId, setThreadId] = useState(() => stored?.threadId ?? createThreadId())
  const [companyInfo, setCompanyInfo] = useState(null)
  const [isSending, setIsSending] = useState(false)

  const nextId = useRef(0)
  const newMessageId = (suffix) => `${(nextId.current += 1)}-${suffix}`

  // Fetch company info once
  useEffect(() => {
    let cancelled = false
    getCompanyInfo()
      .then((info) => {
        if (cancelled || !info) return
        setCompanyInfo(info)
        // Update the welcome message with actual company name (only if still on initial state)
        setMessages((prev) =>
          !stored && prev.length === 1 && prev[0].id === 'welcome'
            ? [buildWelcomeMessage(info.name || DEFAULT_COMPANY_NAME)]
            : prev,
        )
      })
      .catch((error) => console.warn('[app] failed to load company info', error))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist to localStorage whenever messages or threadId change
  useEffect(() => {
    setStored({ threadId, messages })
  }, [threadId, messages, setStored])

  const sendMessage = useCallback(
    async (question) => {
      const userMessage = { id: newMessageId('user'), role: 'user', content: question }
      setMessages((prev) => [...prev, userMessage])
      setIsSending(true)

      try {
        const result = await apiSendMessage(question, threadId)
        setThreadId(result.thread_id)
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId('assistant'),
            role: 'assistant',
            content: result.answer,
            response_type: result.response_type || 'normal',
            product: result.product,
            candidates: result.candidates,
            confidence: result.confidence,
          },
        ])
      } catch (error) {
        console.error('[app] send message failed', error)
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId('error'),
            role: 'assistant',
            content: `Something went wrong: ${error.message}`,
            isError: true,
          },
        ])
      } finally {
        setIsSending(false)
      }
    },
    [threadId],
  )

  const resetChat = useCallback(() => {
    clearStored()
    setMessages([buildWelcomeMessage(companyInfo?.name || DEFAULT_COMPANY_NAME)])
    setThreadId(createThreadId())
  }, [companyInfo, clearStored])

  return {
    messages,
    isSending,
    companyInfo,
    sendMessage,
    resetChat,
    companyName: companyInfo?.name || DEFAULT_COMPANY_NAME,
  }
}
```


## `src/hooks/useLocalStorage.js`

```javascript
import { useState, useCallback } from 'react'

/**
 * Persist state in localStorage with automatic JSON serialisation.
 *
 * Falls back gracefully when storage is unavailable (private browsing,
 * quota exceeded, etc.).
 *
 * @template T
 * @param {string}  key           localStorage key
 * @param {T}       initialValue  default when nothing is stored
 * @returns {[T, (value: T | ((prev: T) => T)) => void, () => void]}
 */
export function useLocalStorage(key, initialValue) {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : initialValue
    } catch {
      return initialValue
    }
  })

  const setValue = useCallback(
    (value) => {
      setStoredValue((prev) => {
        const next = typeof value === 'function' ? value(prev) : value
        try {
          localStorage.setItem(key, JSON.stringify(next))
        } catch {
          // storage full or disabled — state still updates in memory
        }
        return next
      })
    },
    [key],
  )

  const removeValue = useCallback(() => {
    try {
      localStorage.removeItem(key)
    } catch {
      // ignore
    }
    setStoredValue(initialValue)
  }, [key, initialValue])

  return [storedValue, setValue, removeValue]
}
```


## `src/hooks/useScrollToBottom.js`

```javascript
import { useEffect, useRef } from 'react'

/**
 * Returns a ref to attach to a sentinel element at the bottom of a
 * scrollable container. Scrolls into view whenever any dependency changes.
 *
 * @param {any[]} deps  Values that trigger a scroll when they change
 * @returns {React.RefObject<HTMLElement>}
 */
export function useScrollToBottom(deps) {
  const ref = useRef(null)

  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}
```


## `src/index.css`

```css
/* index.css — Global reset + design tokens (Emerald & Champagne)
   ───────────────────────────────────────────────────────────── */

*,
*::before,
*::after {
  box-sizing: border-box;
}

* {
  margin: 0;
  padding: 0;
}

html,
body,
#root {
  height: 100%;
}

:root {
  /* Backgrounds */
  --bg-void: #05070a;
  --bg-deep: #0a0f14;

  /* Emerald accents */
  --accent-primary: #10b981;
  --accent-bright:  #34d399;
  --accent-soft:    #6ee7b7;
  --accent-deep:    #065f46;

  /* Champagne accents */
  --amber-primary:  #f0d9a0;
  --amber-bright:   #fff5db;
  --amber-deep:     #c9a266;
  --amber-glow:     rgba(240, 217, 160, 0.28);

  /* Surfaces */
  --surface-glass:     rgba(10, 15, 20, 0.72);
  --surface-card:      rgba(255, 255, 255, 0.035);
  --surface-hover:     rgba(255, 255, 255, 0.075);
  --assistant-bubble:  rgba(255, 255, 255, 0.045);

  /* Borders */
  --border-subtle:     rgba(255, 255, 255, 0.07);
  --border-light:      rgba(255, 255, 255, 0.11);
  --border-highlight:  rgba(255, 255, 255, 0.18);
  --border-amber:      rgba(240, 217, 160, 0.34);
  --border-emerald:    rgba(16, 185, 129, 0.32);

  /* Text */
  --text-main:      #f3f1ec;
  --text-secondary: #a9a7b6;
  --text-muted:     #6f6d7e;

  /* Radii */
  --radius-sm:   10px;
  --radius-md:   14px;
  --radius-lg:   18px;
  --radius-full: 999px;

  /* Shadows */
  --shadow-amber:   0 0 22px rgba(240, 217, 160, 0.18);
  --shadow-emerald: 0 6px 24px rgba(16, 185, 129, 0.32);

  /* Motion */
  --ease-premium: cubic-bezier(0.16, 1, 0.3, 1);
}

body {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg-void);
  color: var(--text-main);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

button {
  font-family: inherit;
  cursor: pointer;
  border: none;
  background: none;
  color: inherit;
}

input,
textarea {
  font-family: inherit;
  color: inherit;
}

a {
  color: inherit;
  text-decoration: none;
}

/* ─── Screen-reader-only utility ─────────────────────── */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Visible on focus (skip link) */
.sr-only-focusable:focus {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 9999;
  width: auto;
  height: auto;
  padding: 8px 16px;
  margin: 0;
  overflow: visible;
  clip: auto;
  white-space: normal;
  background: var(--accent-primary);
  color: #fff;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 0.9rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

/* ─── Loading text (Suspense fallback) ───────────────── */
.loading-text {
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 12px 0;
}

/* ─── Error boundary ─────────────────────────────────── */
.error-boundary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  text-align: center;
  min-height: 200px;
}

.error-boundary-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-main);
}

.error-boundary-message {
  font-size: 0.95rem;
  color: var(--text-secondary);
  max-width: 42ch;
}

.error-boundary-details {
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--surface-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 10px 16px;
  max-width: 60ch;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.error-boundary-button {
  margin-top: 8px;
  padding: 10px 22px;
  border-radius: var(--radius-full);
  background: var(--accent-primary);
  color: #fff;
  font-weight: 600;
  font-size: 0.9rem;
  border: none;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s var(--ease-premium);
}

.error-boundary-button:hover {
  background: var(--accent-bright);
  transform: translateY(-1px);
}

.error-boundary-button:active {
  transform: translateY(0) scale(0.97);
}
```


## `src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import App from './App.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
```


## `src/test/setup.js`

```javascript
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom doesn't implement scrollIntoView -- App.jsx calls it to keep the
// chat scrolled to the latest message. A no-op is all tests need.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Vitest doesn't auto-run React Testing Library's cleanup between tests
// unless `test.globals: true` is set (it isn't, deliberately, so test files
// import describe/it/expect explicitly) -- so do it here instead, once,
// for every test file.
afterEach(() => {
  cleanup()
})
```


## `src/utils/format.js`

```javascript
/**
 * Shared formatting utilities.
 * Single source of truth — no duplicates across components.
 */

/**
 * Format a numeric value as Indian Rupee string.
 * @param {number|string|null} value
 * @returns {string|null}
 */
export function formatINR(value) {
  if (value == null) return null
  const number = Number(value)
  if (Number.isNaN(number)) return null
  return `₹${Math.round(number).toLocaleString('en-IN')}`
}

/**
 * Parse a spec value (e.g. "8 GB", "1 TB", "5,000 mAh") into a number.
 * Understands TB → multiply by 1000.
 * @param {*} value
 * @returns {number|null}
 */
export function parseSpecNumber(value) {
  if (value == null) return null
  if (typeof value === 'number') return Number.isNaN(value) ? null : value
  const text = String(value).trim()
  if (!text) return null
  const match = text.match(/[\d,]+(?:\.\d+)?/)
  if (!match) return null
  let number = parseFloat(match[0].replace(/,/g, ''))
  if (text.toLowerCase().includes('tb')) number *= 1000
  return Number.isNaN(number) ? null : number
}

/**
 * Split a paragraph into individual sentences for display as a list.
 * @param {string} text
 * @returns {string[]}
 */
export function splitSentences(text) {
  if (!text) return []
  return text
    .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * Format a spec value for table display.
 * Handles null, boolean, arrays, objects, and primitives.
 * @param {*} value
 * @returns {string}
 */
export function formatSpecValue(value) {
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') {
    try {
      return Object.entries(value)
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join(', ')
    } catch {
      return '—'
    }
  }
  return String(value)
}

/**
 * Build a Google Maps search URL.
 * @param {string} query
 * @returns {string}
 */
export function mapsSearchUrl(query) {
  return `https://www.google.com/maps/search/${encodeURIComponent(query)}`
}
```


## `src/utils/scores.js`

```javascript
/**
 * Score & top-picks shape helpers.
 * Single source of truth — shared by ChatMessage, TopPicks and CandidateScores.
 */

/**
 * Convert a raw score (typically 0–1) into a clamped 0–100 integer percentage.
 * @param {number|null|undefined} value
 * @returns {number}
 */
export function getScorePercentage(value) {
  return Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100)
}

/**
 * Map a score percentage to a qualitative tier used for styling.
 * @param {number} pct  0–100
 * @returns {'high'|'medium'|'low'}
 */
export function getScoreTier(pct) {
  if (pct >= 75) return 'high'
  if (pct >= 50) return 'medium'
  return 'low'
}

/**
 * Does this object look like a single category's top-picks payload?
 * i.e. `{ top_picks: [...] }` with at least one pick.
 * @param {*} value
 * @returns {boolean}
 */
export function isTopPicksShape(value) {
  return (
    value != null &&
    typeof value === 'object' &&
    Array.isArray(value.top_picks) &&
    value.top_picks.length > 0
  )
}

/**
 * Does this recommendation product contain any top picks, whether as a
 * single category shape or a multi-category map of them?
 * @param {*} product
 * @returns {boolean}
 */
export function hasTopPicks(product) {
  if (!product || typeof product !== 'object') return false
  if (isTopPicksShape(product)) return true
  return Object.values(product).some((value) => isTopPicksShape(value))
}
```


## `src/utils/specRules.js`

```javascript
/**
 * Spec-quality evaluation rules.
 * Centralised so TopPicks and any future component share the same logic.
 */

export const SPEC_LABELS = Object.freeze({
  brand: 'Brand',
  processor: 'Processor',
  ram: 'RAM',
  storage: 'Storage',
  color: 'Color',
  type: 'Type',
  quality: 'Sound quality',
  capacity: 'Capacity',
  star_rating: 'Energy rating',
  screen_size: 'Screen size',
  resolution: 'Resolution',
  display: 'Display',
  battery: 'Battery',
  battery_life: 'Battery life',
  camera: 'Camera',
  connectivity: 'Connectivity',
  power: 'Power',
  speed_settings: 'Speed settings',
  spin_speed: 'Spin speed',
  jars: 'Jars',
  defrost: 'Defrost',
  inverter: 'Inverter',
  smart_features: 'Smart features',
  noise_cancellation: 'Noise cancellation',
  water_resistance: 'Water resistance',
})

/* ── helper parsers ────────────────────────────────────── */

function parseFirstInt(v) {
  if (v == null) return null
  const m = String(v).match(/(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

function parseFirstFloat(v) {
  if (v == null) return null
  const m = String(v).match(/(\d+\.?\d*)/)
  return m ? parseFloat(m[1]) : null
}

function lowerStr(v) {
  return v != null ? String(v).toLowerCase() : ''
}

/* ── rules ─────────────────────────────────────────────── */

export const SPEC_QUALITY_RULES = Object.freeze({
  ram: {
    parse: parseFirstInt,
    good: (n) => n >= 8,
    bad: (n) => n <= 4,
    goodLabel: '8 GB+ is great for multitasking',
    badLabel: '4 GB or less may feel sluggish',
  },
  storage: {
    parse(v) {
      if (v == null) return null
      const s = String(v).toLowerCase()
      const m = s.match(/(\d+)/)
      if (!m) return null
      let n = parseInt(m[1], 10)
      if (s.includes('tb')) n *= 1024
      return n
    },
    good: (n) => n >= 256,
    bad: (n) => n <= 64,
    goodLabel: '256 GB+ gives plenty of room',
    badLabel: '64 GB or less fills up fast',
  },
  battery: {
    parse: parseFirstInt,
    good: (n) => n >= 5000,
    bad: (n) => n < 4000,
    goodLabel: '5000 mAh+ lasts all day',
    badLabel: 'Under 4000 mAh may need midday charging',
  },
  battery_life: {
    parse: parseFirstInt,
    good: (n) => n >= 8,
    bad: (n) => n < 5,
    goodLabel: '8+ hours is excellent',
    badLabel: 'Under 5 hours is short',
  },
  rating: {
    parse(v) {
      const n = parseFloat(v)
      return Number.isNaN(n) ? null : n
    },
    good: (n) => n >= 4.3,
    bad: (n) => n < 3.5,
    goodLabel: 'Highly rated by buyers',
    badLabel: 'Below-average user rating',
  },
  star_rating: {
    parse: parseFirstInt,
    good: (n) => n >= 4,
    bad: (n) => n <= 2,
    goodLabel: '4+ star energy rating saves power',
    badLabel: '2 star or less — higher running cost',
  },
  noise_cancellation: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('active') || s.includes('anc'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Active noise cancellation included',
    badLabel: 'No noise cancellation',
  },
  water_resistance: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('ip6') || s.includes('ip5') || s.includes('ipx'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Water/dust resistant',
    badLabel: 'Not water resistant',
  },
  inverter: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('inverter') || s.includes('digital'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Inverter compressor — efficient & quiet',
    badLabel: 'Non-inverter — higher power use',
  },
  capacity: {
    parse: parseFirstInt,
    good: (n) => n >= 250,
    bad: (n) => n < 180,
    goodLabel: '250 L+ suits a family well',
    badLabel: 'Under 180 L may be tight for a family',
  },
  screen_size: {
    parse: parseFirstFloat,
    good: (n) => n >= 15,
    bad: (n) => n < 13,
    goodLabel: 'Large screen for productivity',
    badLabel: 'Compact screen — less workspace',
  },
  resolution: {
    parse(v) {
      if (v == null) return null
      const s = String(v).toLowerCase()
      if (s.includes('4k') || s.includes('2160') || s.includes('uhd')) return 4
      if (s.includes('2k') || s.includes('1440') || s.includes('qhd')) return 3
      if (s.includes('1080') || s.includes('fhd') || s.includes('full hd')) return 2
      if (s.includes('720') || s.includes('hd')) return 1
      return null
    },
    good: (n) => n >= 2,
    bad: (n) => n <= 1,
    goodLabel: 'Full HD or better — sharp visuals',
    badLabel: 'HD only — may look soft on large screens',
  },
})

/**
 * Evaluate a single spec against quality rules.
 * @param {string} key   Spec key (e.g. 'ram')
 * @param {*}      value Raw spec value
 * @returns {{ quality: 'good'|'bad'|'neutral', tip: string|null }}
 */
export function evaluateSpec(key, value) {
  const rule = SPEC_QUALITY_RULES[key]
  if (!rule) return { quality: 'neutral', tip: null }
  const parsed = rule.parse(value)
  if (parsed == null) return { quality: 'neutral', tip: null }
  if (rule.good(parsed)) return { quality: 'good', tip: rule.goodLabel }
  if (rule.bad(parsed)) return { quality: 'bad', tip: rule.badLabel }
  return { quality: 'neutral', tip: null }
}
```


## `vite.config.js`

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api/* calls to the FastAPI backend during development so the
    // browser never has to worry about CORS or hardcoded hosts.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: false,
  },
})
```
