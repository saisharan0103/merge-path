"""Application settings — sourced from env, overridable via .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PatchPilot"
    app_version: str = "0.1.0"
    app_env: str = "local"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/patchpilot.db"
    redis_url: str = "redis://localhost:6379/0"
    workdir: Path = Path("./workspace")

    github_token: str | None = Field(default=None, repr=False)
    git_commit_name: str = "PatchPilot"
    git_commit_email: str = "patchpilot@local"
    encryption_key: str | None = Field(default=None, repr=False)

    codex_binary: str = "codex"
    codex_default_timeout: int = 600
    codex_max_loc_default: int = 200
    codex_fake_mode: bool = True

    buffer_multiplier: float = 2.0
    buffer_min_days: int = 7
    buffer_max_days: int = 21
    grace_days: int = 5
    max_concurrent_runs: int = 3
    min_health_score: int = 40

    seed_user_email: str = "local@patchpilot"
    seed_user_name: str = "Local User"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def repos_dir(self) -> Path:
        return self.workdir / "repos"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
