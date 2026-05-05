"""Strategy summary endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import RepoStrategy, Repository, User
from app.db.session import get_db

router = APIRouter()


@router.get("/strategy/summary")
def strategy_summary(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.user_id == user.id).all()]
    counts = {"green": 0, "yellow": 0, "red": 0, "blacklist": 0}
    cooldown = 0
    if not repo_ids:
        return {**counts, "cooldown_queue_size": 0}
    rows = db.query(RepoStrategy).filter(RepoStrategy.repo_id.in_(repo_ids)).all()
    now = datetime.now(timezone.utc)
    for r in rows:
        if r.current_verdict in counts:
            counts[r.current_verdict] += 1
        if r.current_verdict == "red" and r.next_action_at and r.next_action_at > now:
            cooldown += 1
    return {**counts, "cooldown_queue_size": cooldown}
