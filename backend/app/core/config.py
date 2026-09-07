"""Application configuration.

Every external dependency (Supabase, a real AI provider) is optional. When it is
absent the application falls back to a self-contained adapter so the product is
always runnable for evaluation and local development.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application -------------------------------------------------
    app_name: str = "Nexgile WealthAgent API"
    app_version: str = "1.0.0"
    environment: Literal["local", "development", "staging", "production"] = "local"
    debug: bool = True
    api_prefix: str = "/api"

    # ---- Database ----------------------------------------------------
    # Defaults to a local SQLite file so the stack runs with zero setup.
    # In Supabase/Render set DATABASE_URL to the Postgres connection string.
    database_url: str = "sqlite:///./nexgile.db"
    db_echo: bool = False

    # ---- Supabase (optional) ----------------------------------------
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_storage_bucket: str = "wealthagent-documents"

    # ---- Auth --------------------------------------------------------
    # "local"    -> self-contained JWT auth backed by the users table (default)
    # "supabase" -> verify Supabase Auth access tokens, map to local profile
    auth_provider: Literal["local", "supabase"] = "local"
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 8
    remember_me_ttl_minutes: int = 60 * 24 * 30

    # ---- AI ----------------------------------------------------------
    # AI_API_KEY is intentionally optional: the app must run without it.
    ai_provider: Literal["mock", "anthropic", "openai"] = "mock"
    ai_api_key: str | None = None
    ai_model: str = "claude-opus-5"
    ai_timeout_seconds: float = 30.0

    # ---- Files -------------------------------------------------------
    storage_backend: Literal["local", "supabase"] = "local"
    local_storage_dir: str = "./var/documents"
    max_upload_bytes: int = 25 * 1024 * 1024
    allowed_upload_extensions: str = "pdf,doc,docx,xls,xlsx,csv,png,jpg,jpeg,txt,md"

    # ---- CORS --------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- Demo --------------------------------------------------------
    enable_demo_accounts: bool = True
    demo_password: str = "Demo1234!"
    base_currency: str = "USD"

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Supabase / Render hand out `postgres://`; SQLAlchemy 2 wants a driver.
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+psycopg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_extension_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_upload_extensions.split(",") if e.strip()}

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def ai_is_live(self) -> bool:
        return self.ai_provider != "mock" and bool(self.ai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
