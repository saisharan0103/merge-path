"""PR schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TractionPoint(BaseModel):
    scored_at: datetime | None = None
    comments_count: int = 0
    maintainer_engaged: bool = False
    reactions_count: int = 0
    changes_requested: bool = False
    approved: bool = False
    traction_score: int = 0
    verdict: str | None = None


class PRRow(BaseModel):
    id: int
    repo_id: int
    type: str | None = None
    issue_id: int | None = None
    no_brainer_id: int | None = None
    upstream_pr_number: int | None = None
    upstream_url: str | None = None
    title: str | None = None
    fork_branch_name: str | None = None
    files_changed_count: int | None = None
    loc_added: int | None = None
    loc_removed: int | None = None
    status: str | None = None
    opened_at: datetime | None = None
    buffer_until: datetime | None = None
    grace_until: datetime | None = None
    latest_traction: TractionPoint | None = None


class PRDetail(PRRow):
    body: str | None = None
    repo: dict[str, Any] | None = None
    issue: dict[str, Any] | None = None
    fork_branch_sha: str | None = None
    patch: dict[str, Any] | None = None
    traction_history: list[TractionPoint] = []
