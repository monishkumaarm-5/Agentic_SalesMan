"""
Copy this file to config.py and either edit the values directly, or leave
them as os.getenv(...) calls and provide the real values as environment
variables / a local .env file instead (useful for Docker and other
deployments where you don't want secrets baked into a file on disk).

Precedence: a value hardcoded here beats an environment variable; an
environment variable beats the .env file; the .env file beats the
fallback default shown below.
"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is in requirements.txt, but don't hard-fail import of
    # this module just because someone's environment is missing it -- env
    # vars set directly (e.g. by Docker) still work fine without it.
    pass


# --- Google Generative AI (Gemini) ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "your-google-api-key-here")
# Chat model used by every agent (see AGENTS/llm.py).
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
# Leave unset to use the model's default sampling temperature.
LLM_TEMPERATURE = float(os.environ["LLM_TEMPERATURE"]) if os.getenv("LLM_TEMPERATURE") else None

# --- MySQL database credentials ---
DB_USERNAME = os.getenv("DB_USERNAME", "your-db-username")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your-db-password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "your-db-name")

# --- CORS ---
# Comma-separated list of origins the FastAPI backend accepts browser
# requests from. The React dev server (Vite) defaults to port 5173.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)

# --- API auth (optional) ---
# When set to a non-empty value, every /api/* request must send it back as
# an "X-API-Key" header. Leave empty (the default) to keep the API open --
# fine for local development, not recommended once this is reachable by
# anyone but you.
API_KEY = os.getenv("API_KEY", "")

# --- Rate limiting ---
# Max requests per client IP per rolling 60s window on /api/chat. Each chat
# message triggers several LLM calls (a 4-agent CrewAI crew), so this also
# doubles as basic cost protection.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

# --- Timeouts ---
# Hard ceiling, in seconds, on how long a single /api/chat request is
# allowed to run before the API gives up and returns 504. Higher than a
# "simple chatbot" default because a single-category turn now makes several
# more LLM calls than it used to: entry guard, requirement extraction, the
# 4-agent sales crew, the evaluator, and (occasionally) one evaluator-
# triggered retry of the sales crew + a re-evaluation. A multi-category
# question repeats the crew+evaluation portion per category.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Conversation persistence ---
# Where LangGraph's SQLite checkpointer stores conversation state, so chat
# history survives backend restarts. Relative paths resolve from the
# project root (wherever `uvicorn APP.main:app` is launched from).
CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "WORKFLOW/checkpoints.sqlite")

# --- Observability ---
# Where the execution trace log (WORKFLOW/tracing.py) is stored -- routing,
# retrieval candidates/scores, evaluator scores, retries, latency per turn.
TRACE_DB_PATH = os.getenv("TRACE_DB_PATH", "WORKFLOW/traces.sqlite")

# --- Evaluator / retry ---
# Minimum average score (0-1, across groundedness/relevance/product_accuracy/
# constraint_satisfaction/sales_quality) for a sales-agent answer to pass
# the exit evaluator without a retry. See AGENTS/EXIT_SAFE_GAURD_AGENT.py.
EVALUATION_MIN_SCORE = float(os.getenv("EVALUATION_MIN_SCORE", "0.6"))
# Whether a failing evaluation triggers one retry of the sales crew (with
# the evaluator's reasons appended as feedback) before falling back to the
# standard decline message. Disabling this saves LLM calls at the cost of
# occasionally surfacing a weaker first-pass answer.
ENABLE_EVALUATOR_RETRY = os.getenv("ENABLE_EVALUATOR_RETRY", "true").lower() == "true"


# --- Company identity (edit these for your business) ---
# Shown in the assistant's greeting/decline messages, in CrewAI prompts, and
# via the /api/company endpoint -- this is what makes the assistant "your"
# store's assistant instead of a generic one. COMPANY_NAME/WEBSITE/PHONE are
# plain strings so they're easy to override with an env var; STORE_LOCATIONS
# is left as a Python list (like DATABASE/SQL_CONNECTOR.py's TABLES dict)
# because structured, multi-field data doesn't fit comfortably into a single
# env var.
COMPANY_NAME = os.getenv("COMPANY_NAME", "Trein")
COMPANY_TAGLINE = os.getenv(
    "COMPANY_TAGLINE", "Every home, every device -- one store."
)
COMPANY_WEBSITE = os.getenv("COMPANY_WEBSITE", "https://www.trein.example.com")
COMPANY_SUPPORT_PHONE = os.getenv("COMPANY_SUPPORT_PHONE", "1800-000-0000")

# Physical showrooms the assistant can mention when it's relevant (offline
# availability, "where can I see this in person" questions, etc via
# TOOLS/company_tools.py). PLACEHOLDER data -- replace with your real store
# list before this goes anywhere near real customers, same as the
# GOOGLE_API_KEY/DB_* placeholders above.
STORE_LOCATIONS = [
    {
        "name": "Trein T Nagar",
        "city": "Chennai",
        "address": "123 Usman Road, T Nagar, Chennai, Tamil Nadu 600017",
        "phone": "044-4000-1000",
        "hours": "10:00 AM - 9:00 PM, all days",
    },
    {
        "name": "Trein Koramangala",
        "city": "Bengaluru",
        "address": "45 80 Feet Road, Koramangala, Bengaluru, Karnataka 560095",
        "phone": "080-4000-2000",
        "hours": "10:00 AM - 9:00 PM, all days",
    },
    {
        "name": "Trein Banjara Hills",
        "city": "Hyderabad",
        "address": "12 Road No. 3, Banjara Hills, Hyderabad, Telangana 500034",
        "phone": "040-4000-3000",
        "hours": "10:00 AM - 9:00 PM, all days",
    },
]
