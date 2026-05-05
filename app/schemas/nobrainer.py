"""No-brainer schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NoBrainerOut(BaseModel):
    id: int
    repo_id: int
    type: str | None = None
    file: str | None = None
    summary: str | None = None
    proposed_change: str | None = None
    confidence: float | None = None
    status: str
    pr_id: int | None = None
    detected_at: datetime | None = None


class NoBrainerSkipRequest(BaseModel):
    reason: str | None = None
