"""Codex-driven plan/patch stages.

This module bridges the orchestrator and `CodexRunner`. It writes a temp
working directory, builds the prompt by filling placeholders from DB rows,
calls Codex, parses the output, validates against guardrails, and persists
to `fix_plans` / `patches`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.models import (
    FixPlan,
    Issue,
    NoBrainerOpportunity,
    Patch,
    Repository,
    RepositoryPRPatterns,
    RepositoryProfile,
    RepositoryScan,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.codex_runner import CodexInvocation, CodexRunner


def _ensure_workdir(repo_id: int) -> Path:
    p = settings.repos_dir / str(repo_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fill(template: str, mapping: dict[str, Any]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


_PLAN_TEMPLATE = (Path(__file__).parents[2] / "build_docs" / "prompts" / "01_fix_planner.md").read_text(
    encoding="utf-8"
) if (Path(__file__).parents[2] / "build_docs" / "prompts" / "01_fix_planner.md").exists() else ""

_PATCH_TEMPLATE = (Path(__file__).parents[2] / "build_docs" / "prompts" / "02_patch_generator.md").read_text(
    encoding="utf-8"
) if (Path(__file__).parents[2] / "build_docs" / "prompts" / "02_patch_generator.md").exists() else ""


def _budget(patterns: RepositoryPRPatterns | None) -> tuple[int, int]:
    avg_files = float(patterns.avg_files_changed) if patterns and patterns.avg_files_changed else 3.0
    avg_loc = float(patterns.avg_loc_changed) if patterns and patterns.avg_loc_changed else 80.0
    return min(int(avg_files * 1.5), 5), min(int(avg_loc * 1.5), settings.codex_max_loc_default)


def plan(repo_id: int, issue_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        prof = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo_id).first()
        scan = db.query(RepositoryScan).filter(RepositoryScan.repo_id == repo_id).first()
        patterns = db.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo_id).first()
        if not issue or not repo:
            return

        max_files, max_loc = _budget(patterns)
        prompt = _fill(
            _PLAN_TEMPLATE or "produce a fix plan",
            {
                "UPSTREAM_OWNER": repo.upstream_owner,
                "UPSTREAM_NAME": repo.upstream_name,
                "PRIMARY_LANGUAGE": (prof.primary_language if prof else "unknown"),
                "TECH_STACK": ",".join(prof.tech_stack or []) if prof else "",
                "ISSUE_NUMBER": issue.github_number,
                "ISSUE_TITLE": issue.title or "",
                "ISSUE_BODY": (issue.body or "")[:4000],
                "REPRO_STEPS": "see issue body",
                "REPRO_LOG_EXCERPT": (issue.reproduction_log or "")[:1000],
                "STACK_FILE": "",
                "STACK_FUNCTION": "",
                "STACK_LINE": "",
                "SOURCE_DIRS": ",".join(scan.source_dirs or []) if scan else "",
                "TEST_DIRS": ",".join(scan.test_files[:5]) if scan and scan.test_files else "",
                "CANDIDATE_FILES": "\n".join((scan.entrypoints or [])[:10]) if scan else "",
                "MAX_FILES": max_files,
                "MAX_LOC": max_loc,
                "TESTS_STANCE": "required" if (patterns and patterns.test_required) else "encouraged",
                "TESTS_NOTE": "Add a regression test if reasonable.",
                "TITLE_PATTERN": (patterns.title_pattern if patterns else "plain"),
            },
        )

        cwd = _ensure_workdir(repo_id)
        runner = CodexRunner()
        res = runner.invoke(
            CodexInvocation(
                cwd=str(cwd),
                prompt=prompt,
                files_in_scope=[],
                max_loc=0,
                output_target="fix_plan.json",
                timeout_seconds=300,
            )
        )
        emit_log(run_id, "info" if res.success else "warn",
                 f"codex plan: success={res.success} duration={res.duration_seconds:.1f}s",
                 stage="plan_fix")

        plan_data = {}
        if res.output_text:
            try:
                plan_data = json.loads(res.output_text)
            except Exception:
                plan_data = {}

        fp = FixPlan(
            issue_id=issue.id,
            run_id=run_id,
            root_cause=plan_data.get("root_cause"),
            target_files=plan_data.get("target_files") or [],
            target_functions=plan_data.get("target_functions") or [],
            approach=plan_data.get("approach"),
            tests_to_add=plan_data.get("tests_to_add") or [],
            risk_notes=plan_data.get("risk_notes"),
            raw_json=plan_data,
        )
        db.add(fp)
        db.commit()
    finally:
        db.close()


def patch(repo_id: int, issue_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        prof = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo_id).first()
        patterns = db.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo_id).first()
        fp = (
            db.query(FixPlan)
            .filter(FixPlan.issue_id == issue_id)
            .order_by(FixPlan.id.desc())
            .first()
        )
        if not issue or not repo:
            return

        _, max_loc = _budget(patterns)
        target_files = (fp.target_files if fp else None) or ["README.md"]

        prompt = _fill(
            _PATCH_TEMPLATE or "produce the smallest patch",
            {
                "UPSTREAM_OWNER": repo.upstream_owner,
                "UPSTREAM_NAME": repo.upstream_name,
                "PRIMARY_LANGUAGE": prof.primary_language if prof else "unknown",
                "TEST_COMMAND": (prof.test_commands or [""])[0] if prof else "",
                "LINT_COMMAND": (prof.lint_commands or [""])[0] if prof else "",
                "ISSUE_NUMBER": issue.github_number,
                "ISSUE_TITLE": issue.title or "",
                "ISSUE_BODY_SHORT": (issue.body or "")[:1500],
                "PLAN_ROOT_CAUSE": (fp.root_cause if fp else "(no plan)") or "",
                "PLAN_TARGET_FILES": "\n".join(target_files),
                "TEST_FILES": "",
                "PLAN_APPROACH": (fp.approach if fp else "smallest possible change") or "",
                "PLAN_TESTS_TO_ADD": "\n".join(fp.tests_to_add or []) if fp else "",
                "PLAN_RISK_NOTES": (fp.risk_notes if fp else "") or "",
                "PLAN_OUT_OF_SCOPE": "",
                "MAX_LOC": max_loc,
            },
        )

        cwd = _ensure_workdir(repo_id)
        runner = CodexRunner()
        attempt = 1
        last_res = None
        while attempt <= 3:
            res = runner.invoke(
                CodexInvocation(
                    cwd=str(cwd),
                    prompt=prompt,
                    files_in_scope=target_files,
                    max_loc=max_loc,
                    output_target=None,
                    timeout_seconds=600,
                )
            )
            last_res = res
            ok = res.success and res.diff
            emit_log(
                run_id,
                "info" if ok else "warn",
                f"codex patch attempt={attempt} success={res.success} files_modified={len(res.files_modified)}",
                stage="generate_patch",
            )
            if ok:
                break
            attempt += 1

        loc_added = len(re.findall(r"^\+(?!\+\+)", last_res.diff or "", re.MULTILINE))
        loc_removed = len(re.findall(r"^-(?!--)", last_res.diff or "", re.MULTILINE))
        p = Patch(
            issue_id=issue.id,
            fix_plan_id=fp.id if fp else None,
            run_id=run_id,
            attempt=attempt,
            diff_text=last_res.diff,
            files_modified=last_res.files_modified,
            files_added=last_res.files_added,
            files_deleted=last_res.files_deleted,
            loc_added=loc_added,
            loc_removed=loc_removed,
            codex_stdout=last_res.raw_stdout,
            codex_stderr=last_res.raw_stderr,
            codex_exit_code=last_res.exit_code,
            duration_seconds=last_res.duration_seconds,
            status="generated" if last_res.success and last_res.diff else "failed",
            error=last_res.error,
        )
        db.add(p)
        db.commit()
    finally:
        db.close()


def prepare_no_brainer(repo_id: int, nb_id: int, run_id: int) -> None:
    """Stage that does any pre-codex setup. For v1 we just log."""
    emit_log(run_id, "info", "preparing no-brainer fix workdir", stage="prepare")
    _ensure_workdir(repo_id)


def patch_no_brainer(repo_id: int, nb_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        nb = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
        if not nb:
            return
        cwd = _ensure_workdir(repo_id)
        runner = CodexRunner()
        prompt = (
            "Apply the following documentation improvement to README.md.\n"
            f"Type: {nb.type}\nSummary: {nb.summary}\nProposed change: {nb.proposed_change}\n"
            "Make the smallest possible change. Touch only README.md."
        )
        res = runner.invoke(
            CodexInvocation(
                cwd=str(cwd),
                prompt=prompt,
                files_in_scope=["README.md"],
                max_loc=80,
                timeout_seconds=300,
            )
        )
        emit_log(
            run_id,
            "info" if res.success else "warn",
            f"no-brainer patch success={res.success}",
            stage="generate_patch",
        )
        p = Patch(
            issue_id=None,
            no_brainer_id=nb.id,
            run_id=run_id,
            attempt=1,
            diff_text=res.diff,
            files_modified=res.files_modified,
            files_added=res.files_added,
            files_deleted=res.files_deleted,
            codex_stdout=res.raw_stdout,
            codex_stderr=res.raw_stderr,
            codex_exit_code=res.exit_code,
            duration_seconds=res.duration_seconds,
            status="generated" if res.success and res.diff else "failed",
            error=res.error,
        )
        db.add(p)
        db.commit()
    finally:
        db.close()
