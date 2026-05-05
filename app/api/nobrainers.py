"""No-brainer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import NoBrainerOpportunity, Repository, User
from app.db.session import get_db
from app.pipeline.queue import enqueue_run
from app.schemas.nobrainer import NoBrainerOut, NoBrainerSkipRequest

router = APIRouter()


def _row(n: NoBrainerOpportunity) -> dict:
    return NoBrainerOut(
        id=n.id,
        repo_id=n.repo_id,
        type=n.type,
        file=n.file,
        summary=n.summary,
        proposed_change=n.proposed_change,
        confidence=float(n.confidence) if n.confidence is not None else None,
        status=n.status,
        pr_id=n.pr_id,
        detected_at=n.detected_at,
    ).model_dump()


@router.get("/repos/{repo_id}/no-brainers")
def list_nobrainers(
    repo_id: int,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    q = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.repo_id == repo.id)
    if status:
        q = q.filter(NoBrainerOpportunity.status == status)
    total = q.count()
    rows = (
        q.order_by(NoBrainerOpportunity.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_row(n) for n in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/no-brainers/{nb_id}/approve", status_code=202)
def approve_nobrainer(
    nb_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    nb = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
    if not nb:
        raise HTTPException(status_code=404, detail={"error": "no_brainer_not_found", "message": "no such item"})
    repo = db.query(Repository).filter(Repository.id == nb.repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "no_brainer_not_found", "message": "no such item"})
    if repo.paused:
        raise HTTPException(status_code=409, detail={"error": "repo_paused", "message": "repo is paused"})
    nb.status = "planned"
    run_id = enqueue_run(db, repo_id=repo.id, kind="no_brainer_fix", no_brainer_id=nb.id)
    db.commit()
    return {"run_id": run_id, "kind": "no_brainer_fix", "status": "pending"}


@router.post("/no-brainers/{nb_id}/skip")
def skip_nobrainer(
    nb_id: int,
    body: NoBrainerSkipRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    nb = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
    if not nb:
        raise HTTPException(status_code=404, detail={"error": "no_brainer_not_found", "message": "no such item"})
    nb.status = "skipped"
    db.commit()
    return {"id": nb.id, "status": "skipped"}
