# ── Build stage ──────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Optional build-time settings (see .env.example). Leave VITE_API_BASE_URL
# unset to use the relative /api path that nginx proxies to the backend.
ARG VITE_API_BASE_URL
ARG VITE_API_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_API_KEY=$VITE_API_KEY

RUN npm run build

# ── Runtime stage ────────────────────────────────────────
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
