"""Pipeline run schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunRow(BaseModel):
    id: int
    kind: str
    repo_id: int
    issue_id: int | None = None
    no_brainer_id: int | None = None
    stage: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunDetail(RunRow):
    abandon_reason: str | None = None
    error: str | None = None
    log_count: int = 0


class LogRow(BaseModel):
    id: int
    ts: datetime | None = None
    level: str | None = None
    stage: str | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None
