"""Worker -> SSE log bridge. Emits to Redis pubsub + persists to DB."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db.models import LogEvent
from app.db.session import session_scope
from app.utils.logging import get_logger
from app.utils.redis_client import get_redis

_log = get_logger(__name__)


def emit_log(
    run_id: int,
    level: str,
    message: str,
    stage: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Publish to redis channel and persist to log_events.

    Tolerant of any failure — logging must never break the pipeline.
    """
    ts = datetime.now(timezone.utc)
    event = {
        "run_id": run_id,
        "ts": ts.isoformat(),
        "level": level,
        "stage": stage,
        "message": message,
        "meta": meta or {},
    }

    try:
        get_redis().publish(f"runs:{run_id}", json.dumps(event))
    except Exception as exc:  # pragma: no cover
        _log.warning("redis publish failed: %s", exc)

    db = session_scope()
    try:
        db.add(
            LogEvent(
                run_id=run_id,
                ts=ts,
                level=level,
                stage=stage,
                message=message,
                meta=meta,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        _log.warning("log persist failed: %s", exc)
    finally:
        db.close()


def fetch_recent(run_id: int, limit: int = 200) -> list[dict[str, Any]]:
    """For SSE replay-on-connect."""
    db = session_scope()
    try:
        rows = (
            db.query(LogEvent)
            .filter(LogEvent.run_id == run_id)
            .order_by(LogEvent.ts.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [
            {
                "id": r.id,
                "ts": (r.ts.isoformat() if r.ts else None),
                "level": r.level,
                "stage": r.stage,
                "message": r.message,
                "meta": r.meta or {},
            }
            for r in rows
        ]
    finally:
        db.close()
