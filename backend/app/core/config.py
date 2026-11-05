"""
ArchLens Configuration Settings
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "ArchLens"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API Keys
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./archlens.db"

    # File Storage
    UPLOAD_DIR: str = "data/uploads"
    RESULTS_DIR: str = "data/results"

    # CV Pipeline
    CV_CONFIDENCE_THRESHOLD: float = 0.5
    CV_NMS_THRESHOLD: float = 0.4
    MAX_IMAGE_SIZE: int = 1920

    # LLM Settings
    LLM_MODEL: str = "gpt-4o"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_RETRIES: int = 3

    # Git Analysis
    GIT_MAX_COMMITS: int = 1000
    GIT_BLAME_DEPTH: int = 10

    # Evaluation
    MLFLOW_TRACKING_URI: str = "mlflow"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
