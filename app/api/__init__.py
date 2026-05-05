"""API routers — aggregated under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    activity,
    auth,
    issues,
    metrics,
    nobrainers,
    prs,
    repos,
    runs,
    settings as settings_api,
    strategy,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(repos.router, tags=["repos"])
api_router.include_router(issues.router, tags=["issues"])
api_router.include_router(nobrainers.router, tags=["no-brainers"])
api_router.include_router(prs.router, tags=["prs"])
api_router.include_router(runs.router, tags=["runs"])
api_router.include_router(metrics.router, tags=["metrics"])
api_router.include_router(strategy.router, tags=["strategy"])
api_router.include_router(settings_api.router, tags=["settings"])
api_router.include_router(activity.router, tags=["activity"])
