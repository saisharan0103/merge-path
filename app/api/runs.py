"""Pipeline run endpoints + SSE streaming."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.auth import current_user
from app.config import settings  # noqa: F401  -- imported for env consumers
from app.db.models import LogEvent, PipelineRun, User
from app.db.session import get_db, session_scope
from app.log_bus import fetch_recent
from app.schemas.run import LogRow, RunDetail, RunRow
from app.utils.redis_client import get_redis

router = APIRouter()


def _row(r: PipelineRun) -> dict:
    return RunRow(
        id=r.id,
        kind=r.kind,
        repo_id=r.repo_id,
        issue_id=r.issue_id,
        no_brainer_id=r.no_brainer_id,
        stage=r.stage,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
    ).model_dump()


@router.get("/runs")
def list_runs(
    repo_id: int | None = None,
    status: str | None = None,
    kind: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> dict:
    q = db.query(PipelineRun)
    if repo_id:
        q = q.filter(PipelineRun.repo_id == repo_id)
    if status:
        q = q.filter(PipelineRun.status == status)
    if kind:
        q = q.filter(PipelineRun.kind == kind)
    total = q.count()
    rows = (
        q.order_by(PipelineRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_row(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "no such run"})
    log_count = db.query(LogEvent).filter(LogEvent.run_id == r.id).count()
    return RunDetail(
        **_row(r), abandon_reason=r.abandon_reason, error=r.error, log_count=log_count
    ).model_dump()


@router.get("/runs/{run_id}/logs")
def run_logs(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> dict:
    r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "no such run"})
    q = db.query(LogEvent).filter(LogEvent.run_id == run_id)
    total = q.count()
    rows = (
        q.order_by(LogEvent.ts.asc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return {
        "items": [
            LogRow(
                id=l.id,
                ts=l.ts,
                level=l.level,
                stage=l.stage,
                message=l.message,
                meta=l.meta or {},
            ).model_dump()
            for l in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/runs/{run_id}/stop")
def stop_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "no such run"})
    if r.status not in ("pending", "running", "paused"):
        raise HTTPException(
            status_code=409, detail={"error": "run_not_cancellable", "message": "run already terminal"}
        )
    r.cancel_requested = True
    db.commit()
    return {"id": r.id, "cancel_requested": True}


# -- SSE -----------------------------------------------------------------


def _terminal(status: str | None) -> bool:
    return status in {"succeeded", "failed", "abandoned", "cancelled"}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int, request: Request) -> EventSourceResponse:
    """Server-Sent Events for live run logs.

    1) Replay last 200 events from DB.
    2) Subscribe to redis pubsub `runs:{run_id}` for new events.
    3) Poll run status every loop; emit `event: end` and close on terminal.
    """
    # Existence check upfront so SSE returns 404 rather than empty stream.
    db = session_scope()
    try:
        r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not r:
            raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "no such run"})
        terminal = _terminal(r.status)
    finally:
        db.close()

    async def gen() -> AsyncIterator[dict]:
        for old in fetch_recent(run_id, limit=200):
            yield {"event": "log", "data": json.dumps(old)}

        if terminal:
            yield {"event": "end", "data": json.dumps({"status": "succeeded"})}
            return

        client = get_redis()
        # redis.Redis vs in-memory shim: only the real client has a usable pubsub.
        pubsub = None
        try:
            if hasattr(client, "pubsub"):
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(f"runs:{run_id}")
        except Exception:
            pubsub = None

        try:
            while True:
                if await request.is_disconnected():
                    return

                msg = None
                if pubsub is not None:
                    try:
                        msg = pubsub.get_message(timeout=0.5)
                    except Exception:
                        msg = None
                if msg and msg.get("type") == "message":
                    yield {"event": "log", "data": msg["data"]}

                # poll terminal state
                db2 = session_scope()
                try:
                    cur = db2.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                    status = cur.status if cur else None
                finally:
                    db2.close()
                if _terminal(status):
                    yield {"event": "end", "data": json.dumps({"status": status})}
                    return

                await asyncio.sleep(0.5)
        finally:
            try:
                if pubsub is not None:
                    pubsub.unsubscribe(f"runs:{run_id}")
                    pubsub.close()
            except Exception:
                pass

    return EventSourceResponse(gen())
