"""Metrics endpoints — read-only aggregations of DB state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import (
    Issue,
    PipelineRun,
    PullRequest,
    RepoStrategy,
    Repository,
    User,
)
from app.db.session import get_db

router = APIRouter()

_METRICS = {
    "prs_opened": ("pull_requests", "opened_at"),
    "prs_merged": ("pull_requests", "merged_at"),
    "prs_closed": ("pull_requests", "closed_at"),
    "issues_detected": ("issues", "detected_at"),
    "issues_fixed": ("pull_requests", "merged_at"),
    "runs_succeeded": ("pipeline_runs_success", "finished_at"),
    "runs_failed": ("pipeline_runs_fail", "finished_at"),
}


@router.get("/metrics/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repos = db.query(Repository).filter(Repository.user_id == user.id).all()
    repo_ids = [r.id for r in repos]
    if not repo_ids:
        return {
            "total_repos": 0,
            "active_repos": 0,
            "total_prs": 0,
            "open_prs": 0,
            "merged_prs": 0,
            "closed_prs": 0,
            "merge_rate": 0,
            "verdict_distribution": {"green": 0, "yellow": 0, "red": 0, "blacklist": 0},
        }

    active = sum(1 for r in repos if not r.paused and r.health_verdict in ("alive", "weak"))
    prs = db.query(PullRequest).filter(PullRequest.repo_id.in_(repo_ids)).all()
    open_prs = sum(1 for p in prs if p.status == "open")
    merged = sum(1 for p in prs if p.status == "merged")
    closed = sum(1 for p in prs if p.status == "closed")
    terminal = merged + closed
    merge_rate = round(merged / terminal, 4) if terminal else 0

    distribution = {"green": 0, "yellow": 0, "red": 0, "blacklist": 0}
    strategies = (
        db.query(RepoStrategy).filter(RepoStrategy.repo_id.in_(repo_ids)).all() if repo_ids else []
    )
    for s in strategies:
        if s.current_verdict in distribution:
            distribution[s.current_verdict] += 1
    return {
        "total_repos": len(repos),
        "active_repos": active,
        "total_prs": len(prs),
        "open_prs": open_prs,
        "merged_prs": merged,
        "closed_prs": closed,
        "merge_rate": merge_rate,
        "verdict_distribution": distribution,
    }


def _bucket(d: datetime, period: str) -> str:
    if period == "daily":
        return d.strftime("%Y-%m-%d")
    if period == "weekly":
        iso_year, iso_week, _ = d.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return d.strftime("%Y-%m")


@router.get("/metrics/timeseries")
def timeseries(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    metric: str = Query("prs_opened"),
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if metric not in _METRICS:
        return {"period": period, "metric": metric, "series": []}
    repos = db.query(Repository.id).filter(Repository.user_id == user.id).all()
    repo_ids = [r[0] for r in repos]
    if not repo_ids:
        return {"period": period, "metric": metric, "series": []}

    now = datetime.now(timezone.utc)
    default_from = now - timedelta(days=30)
    fr = datetime.fromisoformat(from_) if from_ else default_from
    upto = datetime.fromisoformat(to) if to else now

    rows: list[datetime] = []
    if metric == "prs_opened":
        rows = [r.opened_at for r in db.query(PullRequest).filter(
            PullRequest.repo_id.in_(repo_ids), PullRequest.opened_at >= fr, PullRequest.opened_at <= upto
        ).all() if r.opened_at]
    elif metric in {"prs_merged", "issues_fixed"}:
        rows = [r.merged_at for r in db.query(PullRequest).filter(
            PullRequest.repo_id.in_(repo_ids), PullRequest.merged_at >= fr, PullRequest.merged_at <= upto
        ).all() if r.merged_at]
    elif metric == "prs_closed":
        rows = [r.closed_at for r in db.query(PullRequest).filter(
            PullRequest.repo_id.in_(repo_ids), PullRequest.closed_at >= fr, PullRequest.closed_at <= upto
        ).all() if r.closed_at]
    elif metric == "issues_detected":
        rows = [r.detected_at for r in db.query(Issue).filter(
            Issue.repo_id.in_(repo_ids), Issue.detected_at >= fr, Issue.detected_at <= upto
        ).all() if r.detected_at]
    elif metric == "runs_succeeded":
        rows = [r.finished_at for r in db.query(PipelineRun).filter(
            PipelineRun.repo_id.in_(repo_ids),
            PipelineRun.status == "succeeded",
            PipelineRun.finished_at >= fr,
            PipelineRun.finished_at <= upto,
        ).all() if r.finished_at]
    elif metric == "runs_failed":
        rows = [r.finished_at for r in db.query(PipelineRun).filter(
            PipelineRun.repo_id.in_(repo_ids),
            PipelineRun.status.in_(["failed", "abandoned", "cancelled"]),
            PipelineRun.finished_at >= fr,
            PipelineRun.finished_at <= upto,
        ).all() if r.finished_at]

    counts: dict[str, int] = {}
    for d in rows:
        b = _bucket(d, period)
        counts[b] = counts.get(b, 0) + 1
    series = [{"ts": k, "value": v} for k, v in sorted(counts.items())]
    return {"period": period, "metric": metric, "series": series}


@router.get("/metrics/by-repo")
def by_repo(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repos = db.query(Repository).filter(Repository.user_id == user.id).all()
    items: list[dict[str, Any]] = []
    for r in repos:
        prs = db.query(PullRequest).filter(PullRequest.repo_id == r.id).all()
        opened = len(prs)
        merged = sum(1 for p in prs if p.status == "merged")
        open_count = sum(1 for p in prs if p.status == "open")
        terminal = merged + sum(1 for p in prs if p.status == "closed")
        merge_rate = round(merged / terminal, 4) if terminal else 0
        last = max((p.opened_at for p in prs if p.opened_at), default=None)
        items.append(
            {
                "repo_id": r.id,
                "name": f"{r.upstream_owner}/{r.upstream_name}",
                "prs_opened": opened,
                "prs_merged": merged,
                "prs_open": open_count,
                "merge_rate": merge_rate,
                "last_action_at": last.isoformat() if last else None,
            }
        )
    return {"items": items}


@router.get("/metrics/funnel")
def funnel(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.user_id == user.id).all()]
    if not repo_ids:
        return dict(
            issues_detected=0,
            issues_eligible=0,
            issues_reproduced=0,
            issues_fixed=0,
            prs_opened=0,
            prs_merged=0,
        )
    detected = db.query(func.count(Issue.id)).filter(Issue.repo_id.in_(repo_ids)).scalar() or 0
    eligible = (
        db.query(func.count(Issue.id))
        .filter(Issue.repo_id.in_(repo_ids), Issue.eligibility_verdict == "eligible")
        .scalar()
        or 0
    )
    reproduced = (
        db.query(func.count(Issue.id))
        .filter(Issue.repo_id.in_(repo_ids), Issue.reproducibility_confidence != None)  # noqa: E711
        .scalar()
        or 0
    )
    fixed = (
        db.query(func.count(Issue.id))
        .filter(Issue.repo_id.in_(repo_ids), Issue.status.in_(["pr_opened", "merged"]))
        .scalar()
        or 0
    )
    prs_opened = db.query(func.count(PullRequest.id)).filter(PullRequest.repo_id.in_(repo_ids)).scalar() or 0
    prs_merged = (
        db.query(func.count(PullRequest.id))
        .filter(PullRequest.repo_id.in_(repo_ids), PullRequest.status == "merged")
        .scalar()
        or 0
    )
    return {
        "issues_detected": detected,
        "issues_eligible": eligible,
        "issues_reproduced": reproduced,
        "issues_fixed": fixed,
        "prs_opened": prs_opened,
        "prs_merged": prs_merged,
    }
