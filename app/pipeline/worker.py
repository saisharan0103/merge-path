"""ARQ worker entry. Run with::

    arq app.pipeline.worker.WorkerSettings

If ARQ is not installed in the environment, the worker is unused — runs
fall back to inline threaded execution from `app.pipeline.queue`.
"""

from __future__ import annotations

from app.config import settings


async def startup(ctx: dict) -> None:
    pass


async def shutdown(ctx: dict) -> None:
    pass


try:
    from arq.connections import RedisSettings  # type: ignore

    from app.pipeline.queue import run_pipeline_arq
    from app.pipeline.traction_worker import poll_traction

    class WorkerSettings:
        functions = [run_pipeline_arq, poll_traction]
        on_startup = startup
        on_shutdown = shutdown
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        max_jobs = settings.max_concurrent_runs
        cron_jobs: list = []

except Exception:  # pragma: no cover
    class WorkerSettings:  # type: ignore
        functions: list = []
