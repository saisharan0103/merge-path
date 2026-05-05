"""Pipeline orchestrator — state machine driver.

`run_pipeline_sync(run_id)` is the single entry point. It loads the run,
fans out by `kind`, executes the stages, persists state at each step, and
emits log events. Cancellation is honored at the start of every stage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.db.models import (
    Issue,
    NoBrainerOpportunity,
    PipelineRun,
    Repository,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.pipeline.stages import ISSUE_FIX_STAGES, NO_BRAINER_STAGES, ONBOARDING_STAGES
from app.utils.logging import get_logger

_log = get_logger(__name__)


class _Cancelled(Exception):
    pass


def run_pipeline_sync(run_id: int) -> None:
    """Top-level driver. Catches any exception and marks the run failed."""
    db = session_scope()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            _log.warning("run %s not found", run_id)
            return
        repo = db.query(Repository).filter(Repository.id == run.repo_id).first()
        if not repo:
            run.status = "failed"
            run.error = "repo_missing"
            db.commit()
            return
        if repo.paused:
            run.status = "failed"
            run.error = "repo_paused"
            db.commit()
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        emit_log(run.id, "info", f"start {run.kind} pipeline", stage=None, meta={"repo": repo.id})

        try:
            if run.kind in ("onboarding", "rescan"):
                _execute_stages(run.id, repo.id, ONBOARDING_STAGES, _onboarding_stage)
            elif run.kind == "issue_fix":
                _execute_stages(run.id, repo.id, ISSUE_FIX_STAGES, _issue_fix_stage)
            elif run.kind == "no_brainer_fix":
                _execute_stages(run.id, repo.id, NO_BRAINER_STAGES, _no_brainer_stage)
            else:
                raise ValueError(f"unknown kind: {run.kind}")
        except _Cancelled:
            _terminal(run_id, "cancelled", message="cancelled by user")
            return
        except _Abandon as exc:
            _terminal(run_id, "abandoned", abandon_reason=str(exc), message=str(exc))
            return
        except Exception as exc:
            _log.exception("pipeline failed: %s", exc)
            _terminal(run_id, "failed", error=str(exc), message=f"failed: {exc}")
            return

        _terminal(run_id, "succeeded", message="pipeline complete")
    finally:
        db.close()


class _Abandon(Exception):
    """Raised when a stage decides to stop the run (e.g. low repro confidence)."""


# -- stage runner ----------------------------------------------------------


def _check_cancel(run_id: int) -> None:
    db = session_scope()
    try:
        r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if r and r.cancel_requested:
            raise _Cancelled()
    finally:
        db.close()


def _set_stage(run_id: int, stage: str) -> None:
    db = session_scope()
    try:
        r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if r:
            r.stage = stage
            db.commit()
    finally:
        db.close()


def _execute_stages(
    run_id: int,
    repo_id: int,
    stages: list[str],
    handler: Callable[[int, int, str], None],
) -> None:
    for stage in stages:
        if stage == "done":
            break
        _check_cancel(run_id)
        _set_stage(run_id, stage)
        emit_log(run_id, "info", f"-> {stage}", stage=stage)
        handler(run_id, repo_id, stage)


def _terminal(run_id: int, status: str, *, error: str | None = None, abandon_reason: str | None = None, message: str = "") -> None:
    db = session_scope()
    try:
        r = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not r:
            return
        r.status = status
        r.finished_at = datetime.now(timezone.utc)
        if error:
            r.error = error
        if abandon_reason:
            r.abandon_reason = abandon_reason
        db.commit()
        if message:
            emit_log(run_id, "info" if status == "succeeded" else "warn", message, stage=r.stage)
    finally:
        db.close()


# -- handlers --------------------------------------------------------------


def _onboarding_stage(run_id: int, repo_id: int, stage: str) -> None:
    """Dispatch one onboarding stage."""
    from app.services import (
        code_mapper,
        health_scorer,
        issue_scorer,
        no_brainer_scanner,
        pr_pattern_analyzer,
        profiler,
    )

    if stage == "fetch_metadata":
        health_scorer.refresh_metadata(repo_id, run_id)
    elif stage == "score_health":
        health_scorer.score(repo_id, run_id)
    elif stage == "fetch_profile":
        profiler.profile(repo_id, run_id)
    elif stage == "build_code_map":
        code_mapper.build(repo_id, run_id)
    elif stage == "analyze_pr_patterns":
        pr_pattern_analyzer.analyze(repo_id, run_id)
    elif stage == "scan_no_brainers":
        no_brainer_scanner.scan(repo_id, run_id)
    elif stage == "detect_issues":
        issue_scorer.detect(repo_id, run_id)


def _issue_fix_stage(run_id: int, repo_id: int, stage: str) -> None:
    from app.services import (
        comment_planner,
        guardrails,
        codex_pipeline,
        git_ops,
        pr_writer,
        repro_engine,
        traction_scorer,
        validator,
    )

    db = session_scope()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        issue_id = run.issue_id if run else None
    finally:
        db.close()

    if issue_id is None:
        raise _Abandon("no issue attached to issue_fix run")

    if stage == "reproduce":
        ok = repro_engine.run(repo_id, issue_id, run_id)
        if not ok:
            raise _Abandon("repro_confidence_below_threshold")
    elif stage == "plan_fix":
        codex_pipeline.plan(repo_id, issue_id, run_id)
    elif stage == "generate_patch":
        codex_pipeline.patch(repo_id, issue_id, run_id)
    elif stage == "validate":
        validator.run(repo_id, issue_id, run_id)
    elif stage == "guardrail":
        ok, reason = guardrails.check_for_issue(repo_id, issue_id, run_id)
        if not ok:
            raise _Abandon(f"guardrail:{reason}")
    elif stage == "push_branch":
        git_ops.push_for_issue(repo_id, issue_id, run_id)
    elif stage == "post_comment":
        comment_planner.run(repo_id, issue_id, run_id)
    elif stage == "open_pr":
        pr_writer.open_for_issue(repo_id, issue_id, run_id)
    elif stage == "schedule_traction":
        traction_scorer.schedule_initial(repo_id, issue_id=issue_id)


def _no_brainer_stage(run_id: int, repo_id: int, stage: str) -> None:
    from app.services import codex_pipeline, git_ops, guardrails, pr_writer, traction_scorer

    db = session_scope()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        nb_id = run.no_brainer_id if run else None
    finally:
        db.close()
    if nb_id is None:
        raise _Abandon("no_brainer_id missing")

    if stage == "prepare":
        codex_pipeline.prepare_no_brainer(repo_id, nb_id, run_id)
    elif stage == "generate_patch":
        codex_pipeline.patch_no_brainer(repo_id, nb_id, run_id)
    elif stage == "guardrail":
        ok, reason = guardrails.check_for_no_brainer(repo_id, nb_id, run_id)
        if not ok:
            raise _Abandon(f"guardrail:{reason}")
    elif stage == "push_branch":
        git_ops.push_for_no_brainer(repo_id, nb_id, run_id)
    elif stage == "open_pr":
        pr_writer.open_for_no_brainer(repo_id, nb_id, run_id)
    elif stage == "schedule_traction":
        traction_scorer.schedule_initial(repo_id, no_brainer_id=nb_id)
