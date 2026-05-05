"""Patch guardrails — see PRD §K and acceptance_criteria.md K."""

from __future__ import annotations

from app.config import settings
from app.db.models import Patch, RepositoryPRPatterns
from app.db.session import session_scope


_BLOCKED_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",
}
_BLOCKED_GLOBS = (".github/workflows/", "Dockerfile", ".circleci/")


def _file_is_blocked(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in _BLOCKED_FILES:
        return True
    return any(g in path for g in _BLOCKED_GLOBS)


def check_patch(patch: Patch, max_files: int, max_loc: int) -> tuple[bool, str | None]:
    if not patch.diff_text:
        return False, "empty_diff"
    files = list(patch.files_modified or []) + list(patch.files_added or []) + list(patch.files_deleted or [])
    if any(_file_is_blocked(f) for f in files):
        return False, "blocked_file"
    if len(files) > max_files:
        return False, "too_many_files"
    loc = (patch.loc_added or 0) + (patch.loc_removed or 0)
    if loc > max_loc:
        return False, "loc_exceeded"
    return True, None


def check_for_issue(repo_id: int, issue_id: int, run_id: int) -> tuple[bool, str | None]:
    db = session_scope()
    try:
        patch = (
            db.query(Patch)
            .filter(Patch.issue_id == issue_id)
            .order_by(Patch.id.desc())
            .first()
        )
        if not patch:
            return False, "no_patch"
        patterns = db.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo_id).first()
        avg_files = float(patterns.avg_files_changed) if patterns and patterns.avg_files_changed else 3.0
        avg_loc = float(patterns.avg_loc_changed) if patterns and patterns.avg_loc_changed else 80.0
        max_files = min(int(avg_files * 1.5), 5)
        max_loc = min(int(avg_loc * 1.5), settings.codex_max_loc_default)
        ok, reason = check_patch(patch, max_files, max_loc)
        if not ok:
            patch.status = "guardrail_failed"
            patch.error = reason
            db.commit()
        return ok, reason
    finally:
        db.close()


def check_for_no_brainer(repo_id: int, nb_id: int, run_id: int) -> tuple[bool, str | None]:
    db = session_scope()
    try:
        patch = (
            db.query(Patch)
            .filter(Patch.no_brainer_id == nb_id)
            .order_by(Patch.id.desc())
            .first()
        )
        if not patch:
            return False, "no_patch"
        ok, reason = check_patch(patch, max_files=2, max_loc=80)
        if not ok:
            patch.status = "guardrail_failed"
            patch.error = reason
            db.commit()
        return ok, reason
    finally:
        db.close()
