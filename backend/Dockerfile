# Backend image -- FastAPI + LangGraph/CrewAI agent pipeline.
#
# Build from the project root:
#   docker build -t agentic-salesman-backend .
#
# Run (see docker-compose.yml for the full stack with MySQL + frontend):
#   docker run -p 8000:8000 --env-file .env agentic-salesman-backend

FROM python:3.11-slim

WORKDIR /app

# System deps: gcc/build tools are needed by a couple of the ML/DB wheels
# (e.g. some sentence-transformers / pandas transitive deps) that don't ship
# manylinux wheels for every platform. Removed after pip install to keep the
# image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# config.py is gitignored (it holds secrets) so it never makes it into the
# image; real values are supplied at `docker run` time via --env-file / -e,
# which config.py's os.getenv(...) fallbacks pick up directly -- no config.py
# is required at runtime, but copy the dummy in so imports never fail if
# nothing else set it.
RUN [ -f config.py ] || cp config.dummy.py config.py

EXPOSE 8000

# WORKFLOW/chroma_db and WORKFLOW/checkpoints.sqlite are written at runtime;
# mount a volume over WORKFLOW/ (see docker-compose.yml) to persist them
# across container restarts.

CMD ["uvicorn", "APP.main:app", "--host", "0.0.0.0", "--port", "8000"]
