"""Settings + PAT save."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.config import settings as app_settings
from app.db.models import SettingKV, User
from app.db.session import get_db
from app.schemas.settings import PATSet, SettingsOut, SettingsUpdate
from app.services.codex_runner import CodexRunner
from app.services.github_client import GitHubClient, GitHubError
from app.utils.crypto import encrypt

router = APIRouter()


def _kv_get(db: Session, key: str, default):
    row = db.query(SettingKV).filter(SettingKV.key == key).first()
    if row and row.value is not None:
        return row.value.get("v", default) if isinstance(row.value, dict) else row.value
    return default


def _kv_set(db: Session, key: str, value):
    row = db.query(SettingKV).filter(SettingKV.key == key).first()
    if row:
        row.value = {"v": value}
    else:
        db.add(SettingKV(key=key, value={"v": value}))


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    codex_healthy = CodexRunner().health_check()
    return SettingsOut(
        github_pat_set=user.github_pat_encrypted is not None,
        github_username=user.github_username,
        git_commit_email=user.git_commit_email,
        git_commit_name=user.git_commit_name,
        buffer_multiplier=_kv_get(db, "buffer_multiplier", app_settings.buffer_multiplier),
        max_concurrent_runs=_kv_get(db, "max_concurrent_runs", app_settings.max_concurrent_runs),
        min_health_score=_kv_get(db, "min_health_score", app_settings.min_health_score),
        pause_all=_kv_get(db, "pause_all", False),
        codex_binary=app_settings.codex_binary,
        codex_healthy=codex_healthy,
    ).model_dump()


@router.put("/settings")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if body.git_commit_email is not None:
        user.git_commit_email = body.git_commit_email
    if body.git_commit_name is not None:
        user.git_commit_name = body.git_commit_name
    for k in ("buffer_multiplier", "max_concurrent_runs", "min_health_score", "pause_all"):
        v = getattr(body, k)
        if v is not None:
            _kv_set(db, k, v)
    db.commit()
    return get_settings(db, user)


@router.put("/settings/pat")
def set_pat(body: PATSet, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    pat = body.github_pat.strip()
    if not pat:
        raise HTTPException(status_code=400, detail={"error": "pat_invalid", "message": "empty PAT"})
    # Verify the PAT works
    try:
        gh = GitHubClient(pat=pat)
        me = gh.get_authenticated_user()
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail={"error": "pat_invalid", "message": exc.message}) from None
    user.github_pat_encrypted = encrypt(pat)
    user.github_username = me.get("login")
    db.commit()
    return {"github_pat_set": True, "github_username": user.github_username}
