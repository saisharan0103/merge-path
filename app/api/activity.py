"""Activity feed — same shape as /runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import PipelineRun
from app.db.session import get_db
from app.schemas.run import RunRow

router = APIRouter()


@router.get("/activity")
def activity(
    repo_id: int | None = None,
    kind: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(PipelineRun)
    if repo_id:
        q = q.filter(PipelineRun.repo_id == repo_id)
    if kind:
        q = q.filter(PipelineRun.kind == kind)
    if status:
        q = q.filter(PipelineRun.status == status)
    total = q.count()
    rows = (
        q.order_by(PipelineRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [RunRow.model_validate(r, from_attributes=True).model_dump() for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
