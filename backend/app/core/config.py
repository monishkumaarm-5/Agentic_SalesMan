"""
Application settings, read from environment variables (and a local
`.env` file when present). Every value has a development-friendly
default except the secrets, which fall back to obvious placeholders.

    from app.core.config import get_settings
    settings = get_settings()
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "app" / "data"
VAR_DIR = BACKEND_DIR / "var"

PLACEHOLDER_API_KEY = "your-google-api-key-here"

logger = logging.getLogger("salesman.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    google_api_key: str = PLACEHOLDER_API_KEY
    llm_model: str = "gemini-3.1-flash-lite"
    llm_temperature: float | None = 0.4
    # Per LLM call. Kept well under request_timeout_seconds so one slow
    # call can't eat the whole turn.
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 1

    # --- MySQL ---
    db_username: str = "salesman"
    db_password: str = "changeme"
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "retail_shop"

    # --- Storage paths ---
    chroma_dir: Path = VAR_DIR / "chroma"
    checkpoint_db_path: Path = VAR_DIR / "checkpoints.sqlite"
    trace_db_path: Path = VAR_DIR / "traces.sqlite"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- HTTP / security ---
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    api_key: str = ""
    rate_limit_per_minute: int = 30
    request_timeout_seconds: int = 90
    log_level: str = "INFO"

    # --- Conversation behaviour ---
    history_window: int = 12
    candidates_per_category: int = 6
    picks_per_category: int = 3
    # Safety net only: after this many clarifying questions in a row the
    # assistant shows its best options instead of asking yet another one.
    max_clarifying_questions: int = 3
    normalize_catalog_with_llm: bool = True
    # Build the semantic index in the background at startup (recommended);
    # chats use database search until it's ready.
    warm_index_on_startup: bool = True

    # --- Diagnostics ---
    # Log every workflow node: input state, agent used, output, timing.
    log_graph_state: bool = True
    # Also log full LLM prompts and raw structured outputs (verbose).
    log_llm_prompts: bool = True

    # --- Company identity ---
    company_name: str = "Trein"
    company_tagline: str = "Every home, every device -- one store."
    company_website: str = "https://www.trein.example.com"
    company_support_phone: str = "1800-000-0000"
    company_currency: str = "INR"
    stores_file: Path = DATA_DIR / "stores.json"

    @field_validator("llm_temperature", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        return None if value in ("", None) else value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.google_api_key) and self.google_api_key != PLACEHOLDER_API_KEY

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def stores(self) -> list[dict]:
        return load_stores(self.stores_file)


@lru_cache(maxsize=8)
def load_stores(path: Path) -> list[dict]:
    """Physical store locations from a JSON file (a list of objects with
    name/city/address/phone/hours). Missing or invalid file -> no stores."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        logger.warning("Could not read stores file %s: %s", path, exc)
        return []
    return [s for s in data if isinstance(s, dict) and s.get("name")] if isinstance(data, list) else []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings", "BACKEND_DIR", "DATA_DIR", "VAR_DIR"]
