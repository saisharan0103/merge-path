"""Repository schemas — request + response."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RepoCreateRequest(BaseModel):
    upstream_url: str = Field(..., description="github.com/owner/repo")
    fork_url: str = Field(..., description="github.com/your-username/repo")


class RepoSide(BaseModel):
    owner: str
    name: str
    url: str
    default_branch: str | None = None
    verified: bool | None = None


class RepoOut(BaseModel):
    id: int
    upstream: RepoSide
    fork: RepoSide
    language: str | None = None
    stars: int | None = None
    health_score: int | None = None
    health_verdict: str | None = None
    current_phase: str
    paused: bool
    pause_reason: str | None = None
    open_pr_count: int | None = None
    merged_pr_count: int | None = None
    merge_rate: float | None = None
    created_at: datetime
    last_action_at: datetime | None = None


class RepoDetail(RepoOut):
    profile: dict[str, Any] | None = None
    scan: dict[str, Any] | None = None
    pr_patterns: dict[str, Any] | None = None
    strategy: dict[str, Any] | None = None


class PauseRequest(BaseModel):
    reason: str | None = None
