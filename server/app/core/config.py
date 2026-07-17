from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; every field has a sane default so no .env is required.

    Values come from PRECEDENT_-prefixed environment variables, falling back to
    the repo-root .env file (the tuple covers cwd=server/ and cwd=repo root).
    """

    model_config = SettingsConfigDict(
        env_prefix="PRECEDENT_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    port: int = 8000
    data_dir: Path = Path("data/processed")


@lru_cache
def get_settings() -> Settings:
    return Settings()
