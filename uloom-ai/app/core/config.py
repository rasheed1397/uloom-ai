"""Application configuration.

Provider selection is config-driven per Detailed Design Section 5.6:
AI_CHAT_PROVIDER and AI_EMBEDDING_PROVIDER are independently settable even
though they both resolve to "gemini" today (SRS v1.2 / Detailed Design v0.3).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    secret_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://uloom:uloom@localhost:5432/uloom"
    redis_url: str = "redis://localhost:6379/0"

    # --- AI provider selection (Detailed Design Sec.5.6) ---
    ai_chat_provider: str = "gemini"
    ai_embedding_provider: str = "gemini"

    # TODO:: Rename api key(s) and model(s) to be more generic, not provider specific. Unless the current approach is more aligned with best practices. Need to research and confirm.
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # TODO:: May not be needed if provider agnostic approach to be researched above is adopted.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    voyage_api_key: str = ""

    # --- Retrieval tuning (FR-009: admin-configurable without redeploy) ---
    retrieval_top_k: int = 5
    chunk_token_size: int = 512
    similarity_threshold: float = 0.7

    # --- Auth (NFR-004) ---
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 30

    # --- CORS (frontend is a separate origin - SRS Sec.1.3.2 assumes a
    # browser client). Vite's default dev port is the local default; set
    # CORS_ALLOWED_ORIGINS explicitly for staging/prod. ---
    cors_allowed_origins: tuple[str, ...] = ("http://localhost:5173",)


@lru_cache
def get_settings() -> Settings:
    return Settings()
