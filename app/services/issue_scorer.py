"""Issue detection + 0..100 scoring.

Reads upstream issues, applies hard filters, computes a weighted score, and
persists. Hard filters set `eligibility_verdict = 'filtered'` with a
`filter_reason`. Issues that pass become `eligibility_verdict = 'eligible'`.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models import Issue, Repository, User
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.github_client import GitHubClient


_BANNED_LABELS = {"wontfix", "duplicate", "invalid", "discussion", "question", "needs-info"}
_UI_HINTS = ["css", "ui", "layout", "mobile", "browser", "design", "tailwind", "style"]
_VAGUE_HINTS = ["help", "how do i", "is it possible", "?"]
_PAID_SERVICE_HINTS = ["aws", "stripe", "openai api", "twilio", "sendgrid", "credentials"]


def _has_repro_block(body: str | None) -> bool:
    if not body:
        return False
    if "```" in body:
        return True
    return any(h in body.lower() for h in ("steps to reproduce", "reproduction", "to reproduce"))


def _word_count(text: str | None) -> int:
    return len((text or "").split())


def _score_issue(item: dict[str, Any], merged_recently: bool) -> tuple[int, dict[str, int], str | None]:
    """Return (score, breakdown, filter_reason_or_None)."""
    title = item.get("title") or ""
    body = item.get("body") or ""
    labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in (item.get("labels") or [])]
    label_set = {l.lower() for l in labels}

    # Hard filters
    if label_set & _BANNED_LABELS:
        return 0, {}, "banned_label"
    text = (title + " " + body).lower()
    if any(h in text for h in _UI_HINTS):
        return 0, {}, "ui_or_visual"
    if any(h in text for h in _PAID_SERVICE_HINTS):
        return 0, {}, "needs_paid_service"
    if not body or _word_count(body) < 15:
        return 0, {}, "body_too_thin"
    if any(h in title.lower() for h in _VAGUE_HINTS) and not _has_repro_block(body):
        return 0, {}, "vague_question"

    # Score
    breakdown: dict[str, int] = {}
    score = 0
    if _has_repro_block(body):
        breakdown["reproducible"] = 30
        score += 30

    comments = item.get("comments") or 0
    if comments >= 1:
        breakdown["maintainer_commented"] = 15
        score += 15

    body_words = _word_count(body)
    if 50 <= body_words <= 800:
        breakdown["small_scope"] = 15
        score += 15
    elif body_words < 50:
        breakdown["small_scope"] = 5
        score += 5

    if "expected" in body.lower() and "actual" in body.lower():
        breakdown["testability"] = 10
        score += 10

    created = item.get("created_at")
    if created:
        try:
            d = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - d).days <= 90:
                breakdown["recent"] = 10
                score += 10
        except Exception:
            pass

    if merged_recently:
        breakdown["repo_active"] = 10
        score += 10

    if {"good first issue", "help wanted"} & label_set:
        breakdown["welcoming_label"] = 10
        score += 10

    if "?" in title and "how" in title.lower():
        breakdown["vague_penalty"] = -10
        score -= 10

    score = max(0, min(100, score))
    return score, breakdown, None


def detect(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        full = f"{repo.upstream_owner}/{repo.upstream_name}"

        # quick activity hint for scoring bonus
        merged_recently = False
        try:
            merged = gh.list_merged_prs(full, count=10)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            merged_recently = any(
                datetime.fromisoformat((p.get("merged_at") or "").replace("Z", "+00:00")) >= cutoff
                for p in merged if p.get("merged_at")
            )
        except Exception:
            pass

        try:
            items = gh.list_open_issues(full, max_pages=2, per_page=50)
        except Exception as exc:
            emit_log(run_id, "warn", f"issue fetch failed: {exc}", stage="detect_issues")
            return

        new_count = 0
        for item in items:
            number = item.get("number")
            if number is None:
                continue
            existing = (
                db.query(Issue)
                .filter(Issue.repo_id == repo.id, Issue.github_number == number)
                .first()
            )

            score, breakdown, filt = _score_issue(item, merged_recently)
            verdict = "filtered" if filt else "eligible"
            if not filt and score < 40:
                verdict = "low_score"
            labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in (item.get("labels") or [])]

            if existing is None:
                db.add(
                    Issue(
                        repo_id=repo.id,
                        github_number=number,
                        title=item.get("title"),
                        body=item.get("body"),
                        labels=labels,
                        github_state=item.get("state"),
                        github_url=item.get("html_url"),
                        score=score,
                        score_breakdown=breakdown,
                        eligibility_verdict=verdict,
                        filter_reason=filt,
                        status="detected",
                    )
                )
                new_count += 1
            else:
                existing.title = item.get("title") or existing.title
                existing.body = item.get("body") or existing.body
                existing.labels = labels
                existing.github_state = item.get("state") or existing.github_state
                existing.score = score
                existing.score_breakdown = breakdown
                existing.eligibility_verdict = verdict
                existing.filter_reason = filt
        db.commit()
        emit_log(run_id, "info", f"issues detected: new={new_count} total={len(items)}", stage="detect_issues")
    finally:
        db.close()
