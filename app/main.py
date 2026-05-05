"""FastAPI entry point.

Sync by default; the only async path is the SSE endpoint at
``GET /runs/:id/stream`` (registered in `app/api/runs.py`).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings
from app.seed import ensure_migrations, ensure_seed_user
from app.utils.logging import configure_logging, get_logger

_log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(settings.log_level)
    try:
        ensure_migrations()
    except Exception as exc:  # pragma: no cover
        _log.error("migration failed: %s", exc)
        raise
    ensure_seed_user()
    _log.info("PatchPilot %s ready (%s)", settings.app_version, settings.app_env)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Autonomous OSS contribution agent — local single-user app.",
    lifespan=lifespan,
)

# Frontend dev server runs on :3000 by default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api": settings.api_prefix,
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.exception_handler(ValueError)
def value_error_handler(_request, exc: ValueError):  # pragma: no cover
    return JSONResponse(status_code=400, content={"error": "bad_request", "message": str(exc)})
