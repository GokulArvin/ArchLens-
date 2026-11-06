
"""
ArchLens Configuration Settings
Centralized application configuration using Pydantic Settings.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):

    # ─── Application ─────────────────────────────────────────────

    APP_NAME: str = "ArchLens"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ─── API Keys ─────────────────────────────────────────────────

    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # ─── CORS ─────────────────────────────────────────────────────

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]

    # ─── Database ─────────────────────────────────────────────────

    DATABASE_URL: str = "sqlite+aiosqlite:///./archlens.db"

    # ─── File Storage ─────────────────────────────────────────────

    UPLOAD_DIR: str = "data/uploads"
    RESULTS_DIR: str = "data/results"

    # ─── Computer Vision ──────────────────────────────────────────

    CV_CONFIDENCE_THRESHOLD: float = 0.5
    CV_NMS_THRESHOLD: float = 0.4
    MAX_IMAGE_SIZE: int = 1920
    CV_YOLO_MODEL_PATH: str = ""
    CV_ENABLE_REGION_FALLBACK: bool = True

    # ─── LLM Configuration ────────────────────────────────────────

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1

    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 30

    # ─── LLM Response Caching ─────────────────────────────────────

    LLM_CACHE_ENABLED: bool = True
    LLM_CACHE_TTL_SECONDS: int = 3600

    # ─── Git Analysis ─────────────────────────────────────────────

    GIT_MAX_COMMITS: int = 1000
    GIT_BLAME_DEPTH: int = 10

    # ─── Evaluation ───────────────────────────────────────────────

    MLFLOW_TRACKING_URI: str = "mlflow"

    # ─── Environment Configuration ────────────────────────────────

    model_config = SettingsConfigDict(
        env_file=(Path.cwd() / ".env", BACKEND_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
