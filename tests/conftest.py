"""Pytest fixtures.

We set env vars at collection time (`pytest_configure`) so the import of
`app.config` produces the right Settings; we never reload modules at runtime.
Each test gets a fresh DB by truncating tables (much faster + safer than
reloading SQLAlchemy mappers).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

_TMP_ROOT: Path | None = None


def pytest_configure(config) -> None:
    global _TMP_ROOT
    _TMP_ROOT = Path(tempfile.mkdtemp(prefix="patchpilot-tests-"))
    db_path = _TMP_ROOT / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["REDIS_URL"] = "redis://127.0.0.1:0"  # forces fakeredis fallback
    os.environ["WORKDIR"] = str(_TMP_ROOT / "workspace")
    os.environ["CODEX_FAKE_MODE"] = "true"
    os.environ["GITHUB_TOKEN"] = ""
    os.environ["ENCRYPTION_KEY"] = ""

    # Run migrations once at session setup
    from app.seed import ensure_migrations
    ensure_migrations()


def pytest_unconfigure(config) -> None:
    if _TMP_ROOT and _TMP_ROOT.exists():
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)


def _truncate_all() -> None:
    from sqlalchemy import text

    from app.db.session import engine

    table_order = [
        "log_events", "pr_traction", "pull_requests", "validation_results",
        "patches", "issue_comments", "fix_plans", "no_brainer_opportunities",
        "issues", "pipeline_runs", "repository_pr_patterns", "repository_scan",
        "repository_profile", "repository_health_signals", "contribution_rules",
        "repo_strategy", "settings_kv", "repositories", "users",
    ]
    with engine.begin() as conn:
        for t in table_order:
            try:
                conn.execute(text(f"DELETE FROM {t}"))
            except Exception:
                pass


@pytest.fixture()
def tmp_env(tmp_path) -> Iterator[Path]:
    """Per-test isolation: clean tables, point WORKDIR at a fresh tmp."""
    os.environ["WORKDIR"] = str(tmp_path / "workspace")
    # patch the singleton settings.workdir live (avoid reload)
    from app.config import settings as cfg
    cfg.workdir = tmp_path / "workspace"

    _truncate_all()
    from app.seed import ensure_seed_user
    ensure_seed_user()

    yield tmp_path

    _truncate_all()


@pytest.fixture()
def db(tmp_env):
    from app.db.session import session_scope
    s = session_scope()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(tmp_env):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
