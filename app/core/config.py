from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mergepath"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/patchpilot.db"
    workspace_dir: Path = Path("./workspace")
    clone_dir: Path = Path("./workspace/repos")

    github_token: str | None = Field(default=None, repr=False)
    github_client_id: str | None = None
    github_client_secret: str | None = Field(default=None, repr=False)

    codex_cli_path: str = "codex"
    codex_timeout_seconds: int = 1800
    validation_timeout_seconds: int = 600

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
