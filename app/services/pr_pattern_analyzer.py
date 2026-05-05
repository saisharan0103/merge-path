"""Analyze last 20-40 merged PRs to learn merge culture."""

from __future__ import annotations

import re
import statistics
from datetime import datetime
from typing import Any

from app.db.models import (
    Repository,
    RepositoryPRPatterns,
    User,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.github_client import GitHubClient

_TITLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("conventional", re.compile(r"^(\w+)\(([^)]+)\):\s+(.+)$")),
    ("bracket", re.compile(r"^\[([^\]]+)\]\s+(.+)$")),
    ("issue_ref", re.compile(r"^(.+)\s+\(#\d+\)$")),
]


def detect_title_pattern(titles: list[str]) -> str:
    if not titles:
        return "plain"
    n = len(titles)
    counts = {name: sum(1 for t in titles if rx.match(t)) for name, rx in _TITLE_PATTERNS}
    best_name, best_count = max(counts.items(), key=lambda kv: kv[1])
    if best_count / n > 0.4:
        if best_name == "conventional":
            return "fix(<scope>): <desc>"
        if best_name == "bracket":
            return "[<scope>] <desc>"
        if best_name == "issue_ref":
            return "<desc> (#issue)"
    return "plain"


def _classify_files(filenames: list[str]) -> dict[str, bool]:
    has_test = any("test" in f.lower() or "spec" in f.lower() for f in filenames)
    has_docs = any(
        f.lower().endswith((".md", ".rst", ".txt")) or "docs/" in f.lower() for f in filenames
    )
    return {"has_test": has_test, "has_docs": has_docs}


def analyze(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        full = f"{repo.upstream_owner}/{repo.upstream_name}"
        try:
            prs = gh.list_merged_prs(full, count=40)
        except Exception as exc:
            emit_log(run_id, "warn", f"PR fetch failed: {exc}", stage="analyze_pr_patterns")
            return

        if not prs:
            emit_log(run_id, "info", "no merged PRs to analyze", stage="analyze_pr_patterns")
            return

        titles = [p.get("title", "") or "" for p in prs]
        labels: dict[str, int] = {}
        for p in prs:
            for lbl in p.get("labels") or []:
                name = lbl.get("name") if isinstance(lbl, dict) else str(lbl)
                if name:
                    labels[name] = labels.get(name, 0) + 1
        top_labels = sorted(labels, key=lambda k: -labels[k])[:5]

        # Per-PR file inspection — fetch the files endpoint for first 20 PRs to keep it cheap
        files_changed: list[int] = []
        loc_changed: list[int] = []
        with_tests = 0
        with_docs = 0
        sample_count = 0
        sample_numbers: list[int] = []
        review_hours: list[float] = []

        for p in prs[:20]:
            number = p.get("number")
            sample_numbers.append(number)
            try:
                files_resp = gh._request("GET", f"/repos/{full}/pulls/{number}/files",
                                         params={"per_page": 100})
                files = files_resp.body or []
            except Exception:
                files = []
            filenames = [f.get("filename", "") for f in files if isinstance(f, dict)]
            cls = _classify_files(filenames)
            if cls["has_test"]:
                with_tests += 1
            if cls["has_docs"]:
                with_docs += 1
            files_changed.append(len(filenames))
            loc = sum((f.get("additions", 0) or 0) + (f.get("deletions", 0) or 0) for f in files)
            loc_changed.append(loc)

            try:
                created = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
                merged = datetime.fromisoformat(p["merged_at"].replace("Z", "+00:00"))
                review_hours.append((merged - created).total_seconds() / 3600.0)
            except Exception:
                pass
            sample_count += 1

        existing = (
            db.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo.id).first()
        )
        if existing is None:
            existing = RepositoryPRPatterns(repo_id=repo.id)
            db.add(existing)
        existing.sample_size = sample_count
        existing.avg_files_changed = (
            round(sum(files_changed) / len(files_changed), 2) if files_changed else 0.0
        )
        existing.avg_loc_changed = (
            round(sum(loc_changed) / len(loc_changed), 2) if loc_changed else 0.0
        )
        existing.pct_with_tests = round(with_tests / sample_count, 4) if sample_count else 0.0
        existing.pct_with_docs = round(with_docs / sample_count, 4) if sample_count else 0.0
        existing.common_labels = top_labels
        existing.title_pattern = detect_title_pattern(titles)
        existing.median_review_hours = (
            round(statistics.median(review_hours), 2) if review_hours else None
        )
        existing.sample_pr_numbers = sample_numbers
        existing.test_required = (existing.pct_with_tests or 0) > 0.6
        existing.docs_required = (existing.pct_with_docs or 0) > 0.6
        db.commit()

        emit_log(
            run_id,
            "info",
            f"pr patterns: avg_files={existing.avg_files_changed} pct_tests={existing.pct_with_tests}",
            stage="analyze_pr_patterns",
        )
    finally:
        db.close()
