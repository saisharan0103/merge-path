"""Periodic traction polling. Runs every 30 minutes when ARQ is healthy.

Scans `pull_requests` with status=open AND opened_at < now (i.e. all open
PRs we tracked) and updates traction. Runs strategy adapter per repo at the
end so repo verdicts stay current.
"""

from __future__ import annotations

from typing import Any

from app.db.models import PullRequest
from app.db.session import session_scope


async def poll_traction(ctx: dict[str, Any]) -> dict[str, int]:
    return poll_traction_sync()


def poll_traction_sync() -> dict[str, int]:
    from app.services.strategy_adapter import update_for_repo
    from app.services.traction_scorer import update_for_pr

    db = session_scope()
    try:
        prs = db.query(PullRequest).filter(PullRequest.status.in_(("open", "draft"))).all()
        repo_ids = set()
        for pr in prs:
            update_for_pr(pr.id)
            repo_ids.add(pr.repo_id)
    finally:
        db.close()

    for rid in repo_ids:
        try:
            update_for_repo(rid)
        except Exception:
            pass
    return {"prs": len(prs), "repos": len(repo_ids)}
