"""Application settings loaded from environment variables (see docs/env.md)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    env: str = Field(default="development", alias="APP_ENV")
    database_url: str = "postgresql+psycopg://evalops:evalops_dev_password@localhost:5443/evalops"

    jwt_secret: str = "change-me-dev-only-secret-at-least-32-bytes!!"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173"

    # Rate limiting (in-process token bucket per user+route)
    rate_limit_per_minute: int = 240
    login_rate_limit_per_minute: int = 20

    # Upload validation
    max_upload_bytes: int = 5 * 1024 * 1024
    max_cases_per_upload: int = 5000

    # LLM providers
    llm_provider: str = "local"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Black-box HTTP targets (credentials only ever come from env, never the DB)
    nexus_base_url: str = "http://localhost:8101"
    nexus_email: str | None = None
    nexus_password: str | None = None
    datawise_base_url: str = "http://localhost:8102"
    datawise_email: str | None = None
    datawise_password: str | None = None

    # Worker
    run_worker_in_api: bool = True
    worker_poll_seconds: float = 1.0

    # Seed
    demo_user_password: str | None = None

    # Observability
    otel_exporter_otlp_endpoint: str | None = None
    git_sha: str | None = None
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
