"""PR traction scoring + adapter for verdict transitions.

Spec point system (per PRD):
  - maintainer comment       +3
  - reaction                 +1
  - changes requested        -1
  - approved                 +5
  - merged                   +10
  - closed without merge     -5
  - radio silence after grace -2
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import PRTraction, PullRequest, Repository, User
from app.db.session import session_scope
from app.services.github_client import GitHubClient, GitHubError


def _score_signals(*, comments: int, maintainer_engaged: bool, reactions: int,
                    changes_requested: bool, approved: bool, status: str,
                    radio_silence: bool) -> tuple[int, str]:
    score = 0
    if maintainer_engaged:
        score += 3
    score += reactions
    if changes_requested:
        score -= 1
    if approved:
        score += 5
    if status == "merged":
        score += 10
    elif status == "closed":
        score -= 5
    if radio_silence:
        score -= 2

    if score >= 5:
        verdict = "positive"
    elif score <= -2:
        verdict = "negative"
    elif score == 0:
        verdict = "pending"
    else:
        verdict = "neutral"
    return score, verdict


def schedule_initial(repo_id: int, *, issue_id: int | None = None, no_brainer_id: int | None = None) -> None:
    """Insert a 'pending' traction row so dashboards immediately show the PR.

    The actual polling cron (`poll_traction`) handles updates over time.
    """
    db = session_scope()
    try:
        q = db.query(PullRequest).filter(PullRequest.repo_id == repo_id)
        if issue_id:
            q = q.filter(PullRequest.issue_id == issue_id)
        elif no_brainer_id:
            q = q.filter(PullRequest.no_brainer_id == no_brainer_id)
        pr = q.order_by(PullRequest.id.desc()).first()
        if not pr:
            return
        db.add(PRTraction(pr_id=pr.id, traction_score=0, verdict="pending"))
        db.commit()
    finally:
        db.close()


def update_for_pr(pr_id: int) -> None:
    """Fetch the latest GitHub state for one PR and append a traction row."""
    db = session_scope()
    try:
        pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            return
        repo = db.query(Repository).filter(Repository.id == pr.repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        full = f"{repo.upstream_owner}/{repo.upstream_name}"

        comments_count = 0
        maintainer_engaged = False
        reactions = 0
        changes_requested = False
        approved = False
        status = pr.status or "open"

        if pr.upstream_pr_number:
            try:
                p = gh.get_pull(full, pr.upstream_pr_number)
            except GitHubError:
                p = {}

            if p:
                if p.get("merged"):
                    status = "merged"
                    if not pr.merged_at:
                        pr.merged_at = datetime.now(timezone.utc)
                elif p.get("state") == "closed":
                    status = "closed"
                    if not pr.closed_at:
                        pr.closed_at = datetime.now(timezone.utc)
                else:
                    status = "open"

            try:
                cmts = gh.list_pull_comments(full, pr.upstream_pr_number)
                comments_count = len(cmts)
                owner = repo.upstream_owner.lower()
                maintainer_engaged = any(
                    (c.get("user") or {}).get("login", "").lower() == owner for c in cmts
                )
                # reactions are surfaced per comment
                for c in cmts:
                    rxn = c.get("reactions") or {}
                    reactions += sum(int(rxn.get(k, 0) or 0) for k in ("heart", "+1", "rocket", "hooray"))
            except GitHubError:
                pass

            try:
                reviews = gh.list_pull_reviews(full, pr.upstream_pr_number)
                changes_requested = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)
                approved = any(r.get("state") == "APPROVED" for r in reviews)
            except GitHubError:
                pass

        radio_silence = False
        if pr.grace_until and pr.grace_until < datetime.now(timezone.utc):
            if comments_count == 0 and not approved and not changes_requested:
                radio_silence = True

        score, verdict = _score_signals(
            comments=comments_count, maintainer_engaged=maintainer_engaged, reactions=reactions,
            changes_requested=changes_requested, approved=approved, status=status,
            radio_silence=radio_silence,
        )
        pr.status = status
        db.add(
            PRTraction(
                pr_id=pr.id,
                comments_count=comments_count,
                maintainer_engaged=maintainer_engaged,
                reactions_count=reactions,
                changes_requested=changes_requested,
                approved=approved,
                traction_score=score,
                verdict=verdict,
            )
        )
        db.commit()
    finally:
        db.close()
