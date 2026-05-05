"""Queue helpers — enqueue an ARQ job + persist a `pipeline_runs` row.

If ARQ/Redis aren't reachable we still persist the run row and execute it
inline on a background thread (good enough for local dev + tests).
"""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings  # noqa: F401  -- ensures env loads
from app.db.models import PipelineRun
from app.utils.logging import get_logger

_log = get_logger(__name__)


def enqueue_run(
    db: Session,
    *,
    repo_id: int,
    kind: str,
    issue_id: int | None = None,
    no_brainer_id: int | None = None,
) -> int:
    """Insert a `pipeline_runs` row and dispatch.

    Returns the run id. The dispatch tries ARQ first, falls back to a
    threaded inline execution. Either way the row is committed before we
    return.
    """
    run = PipelineRun(
        repo_id=repo_id,
        issue_id=issue_id,
        no_brainer_id=no_brainer_id,
        kind=kind,
        status="pending",
    )
    db.add(run)
    db.flush()
    db.commit()
    run_id = run.id

    _dispatch(run_id)
    return run_id


def _dispatch(run_id: int) -> None:
    """Try ARQ first; fall back to threaded inline execution."""
    try:
        from arq import create_pool  # type: ignore
        from arq.connections import RedisSettings  # type: ignore

        # ARQ requires async; we invoke it synchronously via anyio.from_thread
        import anyio

        async def _enq() -> None:
            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            pool = await create_pool(redis_settings)
            await pool.enqueue_job("run_pipeline", run_id)

        try:
            anyio.from_thread.run(_enq)
            _log.info("queued run_id=%s via ARQ", run_id)
            return
        except Exception:
            anyio.run(_enq)
            _log.info("queued run_id=%s via ARQ", run_id)
            return
    except Exception as exc:
        _log.info("ARQ unavailable (%s); running run_id=%s inline", exc, run_id)
        _run_inline(run_id)


def _run_inline(run_id: int) -> None:
    from app.pipeline.orchestrator import run_pipeline_sync

    t = threading.Thread(target=run_pipeline_sync, args=(run_id,), daemon=True)
    t.start()


# -- ARQ entry --------------------------------------------------------------


async def run_pipeline_arq(ctx: dict[str, Any], run_id: int) -> None:
    """ARQ task wrapper."""
    from app.pipeline.orchestrator import run_pipeline_sync
    import asyncio

    await asyncio.get_running_loop().run_in_executor(None, run_pipeline_sync, run_id)
