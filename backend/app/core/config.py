from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, AnyHttpUrl, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Blockchain Whitepaper Analyzer"
    environment: str = "development"
    log_config_path: Path = Path("backend/app/logging.yaml")
    log_level: str = "INFO"
    log_dir: Path = Path("backend/logs")
    enable_file_logging: bool = True
    enable_json_logs: bool = True
    sentry_dsn: Optional[str] = None

    # Storage
    storage_base_path: Path = Path("backend/app/storage/uploads")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/prism",
        validation_alias="DATABASE_URL"
    )

    # JWT Authentication
    jwt_secret_key: str = Field(default="changeme", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    google_client_id: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")

    # OpenAI / Gemini
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    llm_provider: str = "openai"  # "openai" | "gemini"
    openai_model_mini: str = "gpt-4o-mini"
    openai_model_turbo: str = "gpt-4-turbo"
    gemini_model_flash: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_embedding_model: str = "text-embedding-004"
    embedding_provider: str = "openai"
    embedding_model_openai: str = "text-embedding-3-large"

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"

    # Chroma
    chroma_server_host: Optional[str] = None
    chroma_server_port: Optional[int] = None
    chroma_server_ssl: bool = False
    chroma_server_api_key: Optional[str] = None
    chroma_persist_directory: Optional[Path] = Path("backend/app/storage/chromadb")
    chroma_collection: str = "documents"
    vector_log_dir: Optional[Path] = Path("backend/app/storage/vector_logs")

    # Feature flags
    run_tasks_inline: bool = True
    document_pipeline_enabled: bool = True

    # Agent configuration
    vector_weight: float = 0.7  # Weight for vector search in hybrid retrieval
    bm25_weight: float = 0.3  # Weight for BM25 search in hybrid retrieval
    agent_max_steps: int = 10  # Maximum reasoning steps for agent
    router_confidence_threshold: float = 0.8  # Confidence threshold for intent classification
    tavily_api_key: Optional[str] = None  # API key for Tavily web search
    serpapi_key: Optional[str] = None  # API key for SerpApi web search

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


class UserContext(BaseModel):
    id: str
    email: str
    is_subscriber: bool = False
    access_token: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

