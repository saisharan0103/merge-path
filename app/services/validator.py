"""Validate the most recent patch by running per-stack tests/lints."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.db.models import Patch, RepositoryProfile, ValidationResult
from app.db.session import session_scope
from app.log_bus import emit_log
from app.sandbox.runner import run as run_cmd
from app.sandbox.stack_detector import detect as detect_stack
from app.sandbox.validators import DEFAULT_TIMEOUTS, commands_for


def run(repo_id: int, issue_id: int, run_id: int) -> None:
    """Run test + lint commands and persist results.

    In fake mode (or when the sandbox can't execute the repo) we still record
    a synthetic 'skipped' validation row so downstream stages can proceed.
    """
    db = session_scope()
    try:
        patch = (
            db.query(Patch)
            .filter(Patch.issue_id == issue_id)
            .order_by(Patch.id.desc())
            .first()
        )
        if not patch:
            emit_log(run_id, "warn", "no patch to validate", stage="validate")
            return
        prof = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo_id).first()
        cwd = settings.repos_dir / str(repo_id)
        if not cwd.exists():
            cwd.mkdir(parents=True, exist_ok=True)

        stack = detect_stack(cwd) if cwd.exists() else (prof.primary_language if prof else "other")
        timeout = DEFAULT_TIMEOUTS.get(stack, 600)
        # Prefer profile-derived commands; fall back to defaults.
        test_cmds = (prof.test_commands if prof and prof.test_commands else commands_for(stack, "test"))
        lint_cmds = (prof.lint_commands if prof and prof.lint_commands else commands_for(stack, "lint"))

        # Test
        test_passed = False
        if test_cmds:
            cmd = test_cmds[0]
            res = run_cmd(cmd, cwd=cwd, timeout=min(timeout, 120))
            db.add(
                ValidationResult(
                    patch_id=patch.id,
                    command="test",
                    command_text=cmd,
                    exit_code=res.exit_code,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    duration_seconds=res.duration_seconds,
                    passed=(res.exit_code == 0),
                )
            )
            test_passed = res.exit_code == 0
            emit_log(run_id, "info" if test_passed else "warn",
                     f"validate test cmd='{cmd}' exit={res.exit_code}", stage="validate")
        else:
            db.add(
                ValidationResult(
                    patch_id=patch.id,
                    command="test",
                    command_text="(no test command available)",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    duration_seconds=0,
                    passed=None,
                )
            )

        # Lint
        if lint_cmds:
            cmd = lint_cmds[0]
            res = run_cmd(cmd, cwd=cwd, timeout=120)
            db.add(
                ValidationResult(
                    patch_id=patch.id,
                    command="lint",
                    command_text=cmd,
                    exit_code=res.exit_code,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    duration_seconds=res.duration_seconds,
                    passed=(res.exit_code == 0),
                )
            )

        patch.status = "validated" if test_passed else patch.status or "generated"
        db.commit()
    finally:
        db.close()
