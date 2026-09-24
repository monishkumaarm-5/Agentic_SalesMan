FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build tools for any dependency without a prebuilt wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# config.py is gitignored (it may hold secrets), so a fresh checkout has
# none. The template reads every value from environment variables, which
# docker-compose supplies from backend/.env.
RUN [ -f config.py ] || cp config.dummy.py config.py

RUN useradd --create-home --uid 1000 app && \
    mkdir -p /app/WORKFLOW/chroma_db && \
    chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "APP.main:app", "--host", "0.0.0.0", "--port", "8000"]
