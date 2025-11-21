from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Blockchain Whitepaper Analyzer"
    environment: str = "development"

    # Storage
    storage_base_path: Path = Path("backend/app/storage/uploads")

    # Supabase
    supabase_url: Optional[AnyHttpUrl] = None
    supabase_anon_key: Optional[str] = None

    #openai
    openai_api_key: Optional[str] = None

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"

    # Feature flags
    run_tasks_inline: bool = True
    document_pipeline_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


class UserContext(BaseModel):
    id: str
    email: str
    is_subscriber: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

