"""Idempotent startup: ensure tables + single user exist."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings
from app.db.models import User
from app.db.session import session_scope
from app.utils.logging import get_logger

_log = get_logger(__name__)


def ensure_migrations() -> None:
    """Run `alembic upgrade head`. Safe to call repeatedly."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    Path("./data").mkdir(parents=True, exist_ok=True)
    command.upgrade(cfg, "head")


def ensure_seed_user() -> User:
    """Insert the single user row if missing. Returns the user."""
    db = session_scope()
    try:
        u = db.query(User).first()
        if u:
            return u
        u = User(
            email=settings.seed_user_email,
            github_username=None,
            git_commit_email=settings.git_commit_email,
            git_commit_name=settings.git_commit_name,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        _log.info("seeded user id=%s email=%s", u.id, u.email)
        return u
    finally:
        db.close()
