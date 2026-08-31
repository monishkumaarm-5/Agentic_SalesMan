# Frontend image -- builds the React (Vite) chat UI and serves the static
# output with nginx.
#
# Build from the FRONTEND/ directory:
#   docker build -t agentic-salesman-frontend .
#
# The API base URL is baked in at BUILD time (Vite inlines env vars into the
# bundle), so pass it as a build arg if the backend isn't reachable at the
# default relative /api path, e.g.:
#   docker build --build-arg VITE_API_BASE_URL=https://api.example.com -t agentic-salesman-frontend .

FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
