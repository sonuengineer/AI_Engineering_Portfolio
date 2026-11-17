"""Validated application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://nexus:nexus_local_only@localhost:5441/nexus"
    test_database_url: str = "postgresql+psycopg://nexus:nexus_local_only@localhost:5441/nexus_test"

    jwt_secret: str = Field(default="dev-only-insecure-secret-change-me", min_length=16)
    access_token_minutes: int = 60
    demo_user_password: str = "change-me-demo-password"  # noqa: S105 -- demo-only default; override via DEMO_USER_PASSWORD
    cors_origins: str = "http://localhost:5171"

    llm_provider: Literal["local", "gemini", "openai"] = "local"
    gemini_api_key: str = ""
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_strong: str = "gemini-2.5-pro"
    gemini_embedding_model: str = "gemini-embedding-001"
    openai_api_key: str = ""
    openai_model_fast: str = "gpt-4o-mini"
    openai_model_strong: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_provider: Literal["local", "gemini", "openai"] = "local"

    workflow_token_budget: int = 60_000
    workflow_step_timeout_s: float = 30.0
    workflow_step_max_attempts: int = 3
    max_upload_mb: int = 15
    url_ingest_allowlist: str = "example.com"
    rate_limit_per_minute: int = 60
    # embedded: API process runs an ingestion worker thread (dev); worker: separate process (prod)
    ingestion_mode: Literal["embedded", "worker"] = "embedded"
    storage_dir: str = ""
    # Object storage: "local" filesystem (dev) or "s3" (AWS S3 or any S3-compatible store, e.g. MinIO)
    storage_backend: Literal["local", "s3"] = "local"
    s3_bucket: str = "nexus-documents"
    s3_endpoint_url: str = ""  # empty = AWS; e.g. http://localhost:9000 for MinIO
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""  # empty = boto3 default credential chain (IAM role, env, profile)
    s3_secret_access_key: str = ""

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.app_env == "production":
            if "change-me" in self.jwt_secret or "insecure" in self.jwt_secret:
                raise ValueError("JWT_SECRET must be set to a real secret in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("LLM_PROVIDER=gemini requires GEMINI_API_KEY")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def url_allowlist(self) -> set[str]:
        return {h.strip().lower() for h in self.url_ingest_allowlist.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
