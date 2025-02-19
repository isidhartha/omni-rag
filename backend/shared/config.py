"""Configuration management for OmniRAG."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # ChromaDB
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    chroma_collection: str = Field(default="omnirag_docs", alias="CHROMA_COLLECTION")

    # Database
    database_url: str = Field(
        default="postgresql://omnirag:password@localhost:5432/omnirag",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # Chunking
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    max_results: int = Field(default=10, alias="MAX_RESULTS")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )

    # Storage
    upload_dir: str = Field(default="/tmp/omnirag/uploads", alias="UPLOAD_DIR")
    index_dir: str = Field(default="/tmp/omnirag/index", alias="INDEX_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
