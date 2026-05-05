"""Settings + activity schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsOut(BaseModel):
    github_pat_set: bool
    github_username: str | None = None
    git_commit_email: str | None = None
    git_commit_name: str | None = None
    buffer_multiplier: float
    max_concurrent_runs: int
    min_health_score: int
    pause_all: bool
    codex_binary: str
    codex_healthy: bool


class SettingsUpdate(BaseModel):
    git_commit_email: str | None = None
    git_commit_name: str | None = None
    buffer_multiplier: float | None = None
    max_concurrent_runs: int | None = None
    min_health_score: int | None = None
    pause_all: bool | None = None


class PATSet(BaseModel):
    github_pat: str
