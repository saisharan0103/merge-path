"""No-brainer scanner.

Per `DECISIONS.md` we use **LLM judgment** for each detection type. We send
focused Codex prompts; if Codex is in fake mode (default for tests), the
runner returns a deterministic stub which we still post-process. We also run
some cheap heuristics first to keep the prompt count tied to actual gaps.
"""

from __future__ import annotations

import re
from typing import Any

from app.db.models import (
    NoBrainerOpportunity,
    Repository,
    RepositoryProfile,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.codex_runner import CodexInvocation, CodexRunner

DETECTION_TYPES = [
    "missing_env_docs",
    "broken_link",
    "missing_test_command",
    "missing_prerequisites",
    "no_windows_notes",
    "no_troubleshooting",
    "broken_readme_command",
]


def _detect_missing_env_docs(readme: str | None) -> dict | None:
    if not readme:
        return None
    text = readme.lower()
    if ".env" in text and "environment variable" not in text and "configuration" not in text:
        return {
            "summary": "README references .env but doesn't explain the variables",
            "proposed_change": "Add a 'Configuration' section listing each required env var.",
        }
    return None


def _detect_broken_link(readme: str | None) -> dict | None:
    if not readme:
        return None
    # Crude: any markdown link with empty target or 'TBD' target
    m = re.search(r"\[[^\]]+\]\(\s*\)|\[[^\]]+\]\(TBD\)", readme)
    if m:
        return {
            "summary": "README contains a placeholder/empty link",
            "proposed_change": "Replace placeholder link with a real reference.",
        }
    return None


def _detect_missing_test_command(profile: RepositoryProfile | None, readme: str | None) -> dict | None:
    if profile is None:
        return None
    has_tests = bool(profile.test_commands)
    mentioned_in_readme = readme and re.search(r"\b(pytest|npm test|go test|cargo test|mvn test)\b", readme)
    if has_tests and not mentioned_in_readme:
        return {
            "summary": "Test command exists in repo but is not documented in README",
            "proposed_change": "Add a 'Tests' section showing how to run the test suite.",
        }
    return None


def _detect_missing_prerequisites(profile: RepositoryProfile | None) -> dict | None:
    if profile and not profile.prerequisites:
        return {
            "summary": "README has no Prerequisites/Requirements section",
            "proposed_change": "Add a Prerequisites section listing required language versions and tools.",
        }
    return None


def _detect_no_windows_notes(readme: str | None) -> dict | None:
    if not readme:
        return None
    if "windows" not in readme.lower() and "wsl" not in readme.lower():
        return {
            "summary": "README has no Windows / WSL setup notes",
            "proposed_change": "Add a short paragraph on Windows/WSL setup quirks.",
        }
    return None


def _detect_no_troubleshooting(readme: str | None) -> dict | None:
    if not readme:
        return None
    if "troubleshoot" not in readme.lower() and "common issues" not in readme.lower():
        return {
            "summary": "README has no Troubleshooting / Common issues section",
            "proposed_change": "Add a Troubleshooting section for the top 3 setup pitfalls.",
        }
    return None


def _detect_broken_readme_command(readme: str | None, profile: RepositoryProfile | None) -> dict | None:
    """Heuristic: README mentions an install command not present in the repo's stack."""
    if not readme or not profile:
        return None
    primary = profile.primary_language or ""
    text = readme.lower()
    if primary == "python" and "yarn install" in text:
        return {
            "summary": "README contains a yarn command in a Python project",
            "proposed_change": "Replace 'yarn install' with 'pip install -e .'.",
        }
    if primary in {"javascript", "typescript"} and "pip install" in text:
        return {
            "summary": "README contains pip install in a Node project",
            "proposed_change": "Replace pip install line with the matching npm/pnpm command.",
        }
    return None


_HEURISTICS: list[tuple[str, callable]] = [
    ("missing_env_docs", lambda readme, prof: _detect_missing_env_docs(readme)),
    ("broken_link", lambda readme, prof: _detect_broken_link(readme)),
    ("missing_test_command", lambda readme, prof: _detect_missing_test_command(prof, readme)),
    ("missing_prerequisites", lambda readme, prof: _detect_missing_prerequisites(prof)),
    ("no_windows_notes", lambda readme, prof: _detect_no_windows_notes(readme)),
    ("no_troubleshooting", lambda readme, prof: _detect_no_troubleshooting(readme)),
    ("broken_readme_command", lambda readme, prof: _detect_broken_readme_command(readme, prof)),
]


def _llm_confidence(repo_id: int, run_id: int, kind: str, summary: str) -> float:
    """Use Codex to confirm the heuristic finding. Returns 0.5-1.0 in fake mode.

    In real mode we'd send a prompt asking yes/no + confidence; in fake mode
    we return a deterministic 0.85 so tests are stable.
    """
    runner = CodexRunner()
    if runner.fake:
        return 0.85
    inv = CodexInvocation(
        cwd=str((__import__("app.config").config.settings.repos_dir / str(repo_id))),
        prompt=(
            "You are vetting a no-brainer detection in an OSS repo.\n"
            f"Type: {kind}\n"
            f"Heuristic finding: {summary}\n"
            "Reply with a single line: 'CONFIDENCE=<float between 0 and 1>'"
        ),
        files_in_scope=[],
        max_loc=0,
        timeout_seconds=60,
    )
    res = runner.invoke(inv)
    if not res.success or not res.raw_stdout:
        return 0.5
    m = re.search(r"CONFIDENCE\s*=\s*([0-9.]+)", res.raw_stdout)
    return float(m.group(1)) if m else 0.5


def scan(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        prof = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo.id).first()
        readme = prof.raw_readme if prof else None

        added = 0
        for kind, fn in _HEURISTICS:
            try:
                hit = fn(readme, prof)
            except Exception as exc:  # pragma: no cover
                emit_log(run_id, "warn", f"heuristic {kind} crashed: {exc}", stage="scan_no_brainers")
                continue
            if not hit:
                continue
            existing = (
                db.query(NoBrainerOpportunity)
                .filter(NoBrainerOpportunity.repo_id == repo.id, NoBrainerOpportunity.type == kind)
                .first()
            )
            if existing:
                continue
            confidence = _llm_confidence(repo_id, run_id, kind, hit["summary"])
            db.add(
                NoBrainerOpportunity(
                    repo_id=repo.id,
                    type=kind,
                    file="README.md",
                    summary=hit["summary"],
                    proposed_change=hit["proposed_change"],
                    confidence=round(confidence, 2),
                    status="detected",
                )
            )
            added += 1
        db.commit()
        emit_log(run_id, "info", f"no-brainers detected: {added}", stage="scan_no_brainers")
    finally:
        db.close()
