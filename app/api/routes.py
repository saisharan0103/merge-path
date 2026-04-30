from fastapi import APIRouter

from app.api import control, health, metrics, repos, runs

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(repos.router, prefix="/repos", tags=["repos"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(control.router, prefix="/control", tags=["control"])
