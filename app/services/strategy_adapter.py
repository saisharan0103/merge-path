"""Strategy adapter — derives green/yellow/red/blacklist verdicts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import PRTraction, PullRequest, RepoStrategy, Repository
from app.db.session import session_scope


def _classify(total_score: int, n_prs: int) -> tuple[str, str, str | None]:
    if n_prs == 0:
        return "yellow", "no PRs yet", None
    avg = total_score / n_prs
    if avg >= 4 and n_prs >= 2:
        return "green", f"avg traction {avg:.1f} across {n_prs} PRs", "escalate_to_issues"
    if avg >= 1:
        return "yellow", f"mixed signal (avg {avg:.1f})", "ship_no_brainer"
    if avg <= -3:
        return "blacklist", f"hostile signal (avg {avg:.1f})", "drop"
    return "red", f"low traction (avg {avg:.1f})", "wait"


def update_for_repo(repo_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        prs = db.query(PullRequest).filter(PullRequest.repo_id == repo.id).all()
        if not prs:
            return
        scores: list[int] = []
        for pr in prs:
            t = (
                db.query(PRTraction)
                .filter(PRTraction.pr_id == pr.id)
                .order_by(PRTraction.scored_at.desc())
                .first()
            )
            if t:
                scores.append(t.traction_score or 0)
        n = len(scores)
        total = sum(scores)
        verdict, reason, next_action = _classify(total, n)

        strat = db.query(RepoStrategy).filter(RepoStrategy.repo_id == repo.id).first()
        if strat is None:
            strat = RepoStrategy(repo_id=repo.id, history=[])
            db.add(strat)
        prev = strat.current_verdict
        strat.current_verdict = verdict
        strat.reason = reason
        strat.next_action = next_action
        strat.next_action_at = (
            datetime.now(timezone.utc) + timedelta(days=30) if verdict == "red" else None
        )
        history = list(strat.history or [])
        history.append(
            {
                "verdict": verdict,
                "at": datetime.now(timezone.utc).isoformat(),
                "score_total": total,
                "pr_count": n,
            }
        )
        strat.history = history[-50:]

        if verdict == "red":
            repo.cooldown_until = strat.next_action_at
            repo.current_phase = "cooldown"
        elif verdict == "blacklist":
            repo.current_phase = "blacklist"
            repo.cooldown_until = None
        elif verdict == "green":
            repo.current_phase = "C_continue"
        else:
            repo.current_phase = "B_buffer"

        db.commit()
        if prev != verdict:
            # log transition (no run_id; we use a synthetic 0 — not persisted)
            pass
    finally:
        db.close()
