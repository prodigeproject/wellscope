"""Application settings loaded from the environment and an optional ``.env`` file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DATABASE_FILENAME = "wellscope.db"


class Settings(BaseSettings):
    """Runtime configuration; each field maps to a ``WELLSCOPE_*`` environment variable."""

    model_config = SettingsConfigDict(
        env_prefix="WELLSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "WELLSCOPE_OPENAI_API_KEY"),
    )
    chat_model: str = "gpt-5.4-mini"
    analyzer_model: str = "gpt-5.4-nano"
    embedding_model: str = "text-embedding-3-small"
    data_dir: Path = Path("data/raw")
    output_dir: Path = Path("data/processed")
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    max_question_chars: int = Field(default=1000, ge=50, le=4000)
    rate_limit_per_min: int = Field(default=20, ge=1, le=600)
    llm_timeout_s: float = Field(default=60.0, gt=0, le=170)
    context_token_budget: int = Field(default=16000, ge=2000, le=100_000)
    log_level: LogLevel = "INFO"
    log_questions: bool = False

    @property
    def database_path(self) -> Path:
        """Location of the SQLite projection built by ``wellscope ingest``."""
        return self.output_dir / DATABASE_FILENAME


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
