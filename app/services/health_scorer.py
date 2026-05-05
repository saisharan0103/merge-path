"""Repo health scoring.

Two-pass per `DECISIONS.md`:
  - Fast signals (<5s): last_commit_at, open_pr_count, merged_pr_count_30d, release_count_180d
  - Slow signals: median_review_hours, ci_pass_rate, maintainer_response_rate,
    external_merge_rate, active_contributors_90d

We collapse both passes into a single function for v1 — they're cheap enough
on the GitHub API in practice — but the structure is preserved so a future
optimization can split them.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models import (
    Repository,
    RepositoryHealthSignal,
    User,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.github_client import GitHubClient, GitHubError


def refresh_metadata(repo_id: int, run_id: int) -> None:
    """Fetch language + stars + default branch from GitHub and persist."""
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        try:
            meta = gh.get_repo(f"{repo.upstream_owner}/{repo.upstream_name}")
        except GitHubError as exc:
            emit_log(run_id, "warn", f"metadata fetch failed: {exc.code}", stage="fetch_metadata")
            return
        repo.language = meta.get("language") or repo.language
        repo.stars = meta.get("stargazers_count") or repo.stars
        repo.upstream_default_branch = meta.get("default_branch") or repo.upstream_default_branch
        db.commit()
        emit_log(
            run_id,
            "info",
            f"metadata: lang={repo.language} stars={repo.stars}",
            stage="fetch_metadata",
        )
    finally:
        db.close()


def _hours_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 3600.0


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_signals(gh: GitHubClient, full_name: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    out: dict[str, Any] = {}

    # Fast pass
    commits = gh.list_recent_commits(full_name, count=10)
    last_commit_at: datetime | None = None
    if commits:
        c = commits[0].get("commit", {}).get("committer", {}).get("date")
        last_commit_at = _parse_dt(c)
    out["last_commit_at"] = last_commit_at

    out["open_pr_count"] = gh.list_open_pulls_count(full_name)

    merged = gh.list_merged_prs(full_name, count=40)
    cutoff_30d = now - timedelta(days=30)
    out["merged_pr_count_30d"] = sum(
        1 for p in merged if (_parse_dt(p.get("merged_at")) or now) >= cutoff_30d
    )

    releases = gh.list_releases(full_name, count=30)
    cutoff_180d = now - timedelta(days=180)
    out["release_count_180d"] = sum(
        1 for r in releases if (_parse_dt(r.get("published_at")) or now) >= cutoff_180d
    )

    # Slow pass — use the same merged-PR sample
    review_hours: list[float] = []
    for p in merged:
        c = _parse_dt(p.get("created_at"))
        m = _parse_dt(p.get("merged_at"))
        if c and m:
            review_hours.append(_hours_between(c, m))
    out["median_review_hours"] = (
        round(statistics.median(review_hours), 2) if review_hours else None
    )

    runs = gh.list_workflow_runs(full_name, count=30)
    if runs:
        ok = sum(1 for r in runs if r.get("conclusion") == "success")
        out["ci_pass_rate"] = round(ok / len(runs), 4)
    else:
        out["ci_pass_rate"] = None

    # Active contributors in last 90d (from commits)
    cutoff_90d = now - timedelta(days=90)
    contributors = set()
    for c in commits:
        d = _parse_dt(c.get("commit", {}).get("committer", {}).get("date"))
        if d and d >= cutoff_90d:
            login = (c.get("author") or {}).get("login")
            if login:
                contributors.add(login)
    out["active_contributors_90d"] = len(contributors) or None

    # External merge rate: PRs merged authored by someone other than upstream owner
    if merged:
        owner = full_name.split("/")[0].lower()
        external = sum(
            1 for p in merged if (p.get("user") or {}).get("login", "").lower() != owner
        )
        out["external_merge_rate"] = round(external / len(merged), 4)
    else:
        out["external_merge_rate"] = None

    out["maintainer_response_rate"] = None  # requires per-issue inspection — left for future
    return out


def _score(signals: dict[str, Any]) -> tuple[int, str]:
    """Return (score 0..100, verdict in {alive, weak, stale}). Tolerant of nulls."""
    score = 0
    now = datetime.now(timezone.utc)
    last = signals.get("last_commit_at")
    if isinstance(last, datetime):
        days = (now - last).days
        if days <= 14:
            score += 30
        elif days <= 60:
            score += 18
        elif days <= 180:
            score += 8

    merged_30 = signals.get("merged_pr_count_30d") or 0
    if merged_30 >= 10:
        score += 25
    elif merged_30 >= 3:
        score += 15
    elif merged_30 >= 1:
        score += 7

    rel = signals.get("release_count_180d") or 0
    if rel >= 4:
        score += 10
    elif rel >= 1:
        score += 5

    ci = signals.get("ci_pass_rate")
    if isinstance(ci, (int, float)):
        score += int(min(15, ci * 15))

    ext = signals.get("external_merge_rate")
    if isinstance(ext, (int, float)):
        score += int(min(10, ext * 20))

    mrh = signals.get("median_review_hours")
    if isinstance(mrh, (int, float)):
        if mrh <= 24:
            score += 10
        elif mrh <= 96:
            score += 6
        elif mrh <= 240:
            score += 3

    score = max(0, min(100, score))
    if score >= 60:
        verdict = "alive"
    elif score >= 30:
        verdict = "weak"
    else:
        verdict = "stale"
    return score, verdict


def score(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        full = f"{repo.upstream_owner}/{repo.upstream_name}"
        try:
            signals = compute_signals(gh, full)
        except GitHubError as exc:
            emit_log(run_id, "warn", f"health fetch failed: {exc.code}", stage="score_health")
            return
        s, verdict = _score(signals)
        repo.health_score = s
        repo.health_verdict = verdict
        row = RepositoryHealthSignal(
            repo_id=repo.id,
            last_commit_at=signals.get("last_commit_at"),
            open_pr_count=signals.get("open_pr_count"),
            merged_pr_count_30d=signals.get("merged_pr_count_30d"),
            median_review_hours=signals.get("median_review_hours"),
            release_count_180d=signals.get("release_count_180d"),
            ci_pass_rate=signals.get("ci_pass_rate"),
            active_contributors_90d=signals.get("active_contributors_90d"),
            external_merge_rate=signals.get("external_merge_rate"),
            maintainer_response_rate=signals.get("maintainer_response_rate"),
            alive_score=s,
            raw={
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in signals.items()
            },
        )
        db.add(row)
        db.commit()
        emit_log(run_id, "info", f"health score={s} verdict={verdict}", stage="score_health")
    finally:
        db.close()
