"""Application settings (pydantic-settings). Values come from env vars or a .env file."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_PROJECT_DIR / ".env"), str(_BACKEND_DIR / ".env")),
        extra="ignore",
    )

    app_name: str = "DATAWISE AI"
    environment: str = "dev"

    app_database_url: str = (
        "postgresql+psycopg://datawise:change-me-admin-password@localhost:5442/datawise_app"
    )
    analytics_admin_database_url: str = (
        "postgresql://datawise:change-me-admin-password@localhost:5442/datawise_analytics"
    )
    analytics_reader_database_url: str = (
        "postgresql://datawise_reader:change-me-reader-password@localhost:5442/datawise_analytics"
    )

    jwt_secret: str = Field(default="change-me-dev-only-jwt-secret-at-least-32-characters", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    demo_user_password: str = "change-me-demo-password"

    llm_provider: Literal["local", "gemini", "openai"] = "local"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    max_rows: int = 1000
    statement_timeout_ms: int = 5000
    analytics_as_of_date: date = date(2026, 10, 31)

    cors_origins: str = "http://localhost:5172"
    rate_limit_ask_per_minute: int = 30
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
