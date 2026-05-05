"""Issue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import (
    FixPlan,
    Issue,
    IssueComment,
    Patch,
    PullRequest,
    Repository,
    User,
)
from app.db.session import get_db
from app.pipeline.queue import enqueue_run
from app.schemas.issue import IssueDetail, IssueRow, SkipRequest

router = APIRouter()


def _row(i: Issue) -> dict:
    return IssueRow(
        id=i.id,
        repo_id=i.repo_id,
        github_number=i.github_number,
        title=i.title,
        labels=i.labels or [],
        github_state=i.github_state,
        github_url=i.github_url,
        score=i.score,
        eligibility_verdict=i.eligibility_verdict,
        filter_reason=i.filter_reason,
        reproducibility_confidence=float(i.reproducibility_confidence)
        if i.reproducibility_confidence is not None
        else None,
        status=i.status,
        detected_at=i.detected_at,
    ).model_dump()


@router.get("/repos/{repo_id}/issues")
def list_issues(
    repo_id: int,
    status: str | None = None,
    min_score: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    q = db.query(Issue).filter(Issue.repo_id == repo.id)
    if status:
        q = q.filter(Issue.status == status)
    if min_score is not None:
        q = q.filter(Issue.score >= min_score)
    total = q.count()
    rows = q.order_by(Issue.score.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_row(i) for i in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    i = db.query(Issue).filter(Issue.id == issue_id).first()
    if not i:
        raise HTTPException(status_code=404, detail={"error": "issue_not_found", "message": "no such issue"})
    repo = db.query(Repository).filter(Repository.id == i.repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "issue_not_found", "message": "no such issue"})
    fp = db.query(FixPlan).filter(FixPlan.issue_id == i.id).order_by(FixPlan.id.desc()).first()
    patch = db.query(Patch).filter(Patch.issue_id == i.id).order_by(Patch.id.desc()).first()
    comment = (
        db.query(IssueComment).filter(IssueComment.issue_id == i.id).order_by(IssueComment.id.desc()).first()
    )
    pr = db.query(PullRequest).filter(PullRequest.issue_id == i.id).order_by(PullRequest.id.desc()).first()
    detail = IssueDetail(
        **_row(i),
        body=i.body,
        score_breakdown=i.score_breakdown or {},
        reproduction_log=i.reproduction_log,
        abandon_reason=i.abandon_reason,
        fix_plan=(
            {
                "id": fp.id,
                "root_cause": fp.root_cause,
                "target_files": fp.target_files or [],
                "approach": fp.approach,
            }
            if fp
            else None
        ),
        latest_patch=(
            {
                "id": patch.id,
                "diff_text": patch.diff_text,
                "loc_added": patch.loc_added,
                "loc_removed": patch.loc_removed,
                "status": patch.status,
            }
            if patch
            else None
        ),
        comment=(
            {"id": comment.id, "posted_url": comment.posted_url, "status": comment.status}
            if comment
            else None
        ),
        pr=(
            {
                "id": pr.id,
                "upstream_pr_number": pr.upstream_pr_number,
                "upstream_url": pr.upstream_url,
                "status": pr.status,
            }
            if pr
            else None
        ),
    )
    return detail.model_dump()


@router.post("/issues/{issue_id}/skip")
def skip_issue(
    issue_id: int,
    body: SkipRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    i = db.query(Issue).filter(Issue.id == issue_id).first()
    if not i:
        raise HTTPException(status_code=404, detail={"error": "issue_not_found", "message": "no such issue"})
    i.status = "skipped"
    i.abandon_reason = body.reason
    db.commit()
    return {"id": i.id, "status": "skipped"}


@router.post("/issues/{issue_id}/retry", status_code=202)
def retry_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    i = db.query(Issue).filter(Issue.id == issue_id).first()
    if not i:
        raise HTTPException(status_code=404, detail={"error": "issue_not_found", "message": "no such issue"})
    repo = db.query(Repository).filter(Repository.id == i.repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "issue_not_found", "message": "no such issue"})
    if repo.paused:
        raise HTTPException(status_code=409, detail={"error": "repo_paused", "message": "repo is paused"})
    run_id = enqueue_run(db, repo_id=repo.id, kind="issue_fix", issue_id=i.id)
    db.commit()
    return {"run_id": run_id, "kind": "issue_fix", "status": "pending"}
