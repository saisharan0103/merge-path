"""Issue schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IssueRow(BaseModel):
    id: int
    repo_id: int
    github_number: int
    title: str | None = None
    labels: list[str] = []
    github_state: str | None = None
    github_url: str | None = None
    score: int | None = None
    eligibility_verdict: str | None = None
    filter_reason: str | None = None
    reproducibility_confidence: float | None = None
    status: str
    detected_at: datetime | None = None


class IssueDetail(IssueRow):
    body: str | None = None
    score_breakdown: dict[str, Any] | None = None
    reproduction_log: str | None = None
    abandon_reason: str | None = None
    fix_plan: dict[str, Any] | None = None
    latest_patch: dict[str, Any] | None = None
    comment: dict[str, Any] | None = None
    pr: dict[str, Any] | None = None


class SkipRequest(BaseModel):
    reason: str | None = None
