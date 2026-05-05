"""PR endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import Issue, PRTraction, PullRequest, Repository, User
from app.db.session import get_db
from app.schemas.pr import PRDetail, PRRow, TractionPoint

router = APIRouter()


def _latest_traction(db: Session, pr_id: int) -> TractionPoint | None:
    t = (
        db.query(PRTraction)
        .filter(PRTraction.pr_id == pr_id)
        .order_by(PRTraction.scored_at.desc())
        .first()
    )
    if not t:
        return None
    return TractionPoint(
        scored_at=t.scored_at,
        comments_count=t.comments_count or 0,
        maintainer_engaged=bool(t.maintainer_engaged),
        reactions_count=t.reactions_count or 0,
        changes_requested=bool(t.changes_requested),
        approved=bool(t.approved),
        traction_score=t.traction_score or 0,
        verdict=t.verdict,
    )


def _row(pr: PullRequest, db: Session) -> dict:
    return PRRow(
        id=pr.id,
        repo_id=pr.repo_id,
        type=pr.type,
        issue_id=pr.issue_id,
        no_brainer_id=pr.no_brainer_id,
        upstream_pr_number=pr.upstream_pr_number,
        upstream_url=pr.upstream_url,
        title=pr.title,
        fork_branch_name=pr.fork_branch_name,
        files_changed_count=pr.files_changed_count,
        loc_added=pr.loc_added,
        loc_removed=pr.loc_removed,
        status=pr.status,
        opened_at=pr.opened_at,
        buffer_until=pr.buffer_until,
        grace_until=pr.grace_until,
        latest_traction=_latest_traction(db, pr.id),
    ).model_dump()


@router.get("/prs")
def list_prs(
    repo_id: int | None = None,
    status: str | None = None,
    type: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    q = db.query(PullRequest).join(Repository, Repository.id == PullRequest.repo_id).filter(
        Repository.user_id == user.id
    )
    if repo_id:
        q = q.filter(PullRequest.repo_id == repo_id)
    if status:
        q = q.filter(PullRequest.status == status)
    if type:
        q = q.filter(PullRequest.type == type)
    if from_:
        q = q.filter(PullRequest.opened_at >= datetime.fromisoformat(from_))
    if to:
        q = q.filter(PullRequest.opened_at <= datetime.fromisoformat(to))

    total = q.count()
    rows = (
        q.order_by(PullRequest.opened_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_row(r, db) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/prs/{pr_id}")
def pr_detail(pr_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail={"error": "pr_not_found", "message": "no such PR"})
    repo = db.query(Repository).filter(Repository.id == pr.repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "pr_not_found", "message": "no such PR"})

    history_rows = (
        db.query(PRTraction).filter(PRTraction.pr_id == pr.id).order_by(PRTraction.scored_at.asc()).all()
    )
    history = [
        TractionPoint(
            scored_at=h.scored_at,
            comments_count=h.comments_count or 0,
            maintainer_engaged=bool(h.maintainer_engaged),
            reactions_count=h.reactions_count or 0,
            changes_requested=bool(h.changes_requested),
            approved=bool(h.approved),
            traction_score=h.traction_score or 0,
            verdict=h.verdict,
        )
        for h in history_rows
    ]

    issue = None
    if pr.issue_id:
        i = db.query(Issue).filter(Issue.id == pr.issue_id).first()
        if i:
            issue = {"id": i.id, "title": i.title, "github_number": i.github_number}

    detail = PRDetail(
        **_row(pr, db),
        body=pr.body,
        repo={
            "id": repo.id,
            "upstream": {"owner": repo.upstream_owner, "name": repo.upstream_name, "url": repo.upstream_url},
            "fork": {"owner": repo.fork_owner, "name": repo.fork_name, "url": repo.fork_url},
        },
        issue=issue,
        fork_branch_sha=pr.fork_branch_sha,
        traction_history=history,
    )
    return detail.model_dump()


@router.get("/prs/{pr_id}/traction")
def pr_traction(pr_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail={"error": "pr_not_found", "message": "no such PR"})
    rows = db.query(PRTraction).filter(PRTraction.pr_id == pr.id).order_by(PRTraction.scored_at.asc()).all()
    return {
        "history": [
            {
                "scored_at": r.scored_at.isoformat() if r.scored_at else None,
                "comments_count": r.comments_count or 0,
                "maintainer_engaged": bool(r.maintainer_engaged),
                "reactions_count": r.reactions_count or 0,
                "changes_requested": bool(r.changes_requested),
                "approved": bool(r.approved),
                "traction_score": r.traction_score or 0,
                "verdict": r.verdict,
            }
            for r in rows
        ]
    }
