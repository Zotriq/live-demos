"""
Centralized application configuration.

All configuration is loaded from environment variables (see .env.example).
Using pydantic-settings gives us validation, type coercion, and a single
source of truth instead of scattering os.getenv() calls across the codebase.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # LLM provider selection
    primary_llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Embeddings
    embedding_provider: Literal["openai"] = "openai"
    embedding_model: str = "text-embedding-3-small"

    # Chat models
    openai_chat_model: str = "gpt-4o-mini"
    anthropic_chat_model: str = "claude-sonnet-4-6"

    # Database / vector store
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pdf_rag"
    vector_collection_name: str = "pdf_rag_documents"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.0

    # Security
    api_key: str | None = None
    max_upload_size_mb: int = 25
    allowed_origins: str = "http://localhost:3000"

    # Rate limiting
    rate_limit_per_minute: int = 30

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance so the environment is parsed only once."""
    return Settings()
