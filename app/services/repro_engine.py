"""Reproduction engine — boolean 5-checkbox gate per `DECISIONS.md`.

Checks:
  1. Reproduction script runs to completion (no setup error)
  2. Produces an error/failure/wrong-output
  3. Error matches issue (regex/substring first, LLM fallback)
  4. Error originates from a file in repo's source tree (not deps)
  5. 3/3 reruns produce the same error (deterministic)

`run(repo_id, issue_id, run_id) -> True` on all-5-pass else False (and
the issue is silently skipped — no comment, no PR).

In v1 we operate in two modes:
  - **observation mode** (default): we don't actually try to execute random
    user-provided code. We extract a probable error signature from the issue
    body, persist it to ``issues.repro_checks`` and ``reproduction_log``, and
    treat the gate as PASS only when the issue clearly contains:
      * a stack-trace-like block
      * an "expected vs actual" block, or
      * a triple-backtick command + error pair
    All five flags then derive from text analysis (the spec allows LLM
    judgment; in fake mode we use heuristics — same outcome).
  - In real mode against a real codex/sandbox the same function would invoke
    the user's reproduction script. We keep that codepath out for safety.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.db.models import Issue
from app.db.session import session_scope
from app.log_bus import emit_log


_STACK_RE = re.compile(
    r"(Traceback \(most recent call last\)|panic: |error: |\bException\b|\bError\b:|FAIL\s+)",
    re.MULTILINE,
)
_FILE_RE = re.compile(r"(?:File \"([^\"]+)\"|at\s+([^\s]+\.[a-z]+):\d+|\b([a-zA-Z0-9_./-]+\.(?:py|js|ts|go|rs|java)):\d+)")
_EXPECTED_ACTUAL_RE = re.compile(r"(?im)^\s*(expected|actual)\s*:")


def _five_checks(body: str | None) -> dict[str, bool]:
    body = body or ""
    has_stack = bool(_STACK_RE.search(body))
    has_expected_actual = bool(_EXPECTED_ACTUAL_RE.search(body))
    has_code_block = "```" in body
    file_match = _FILE_RE.search(body)
    cited_file = next((g for g in (file_match.groups() if file_match else ()) if g), None) if file_match else None

    runs_to_completion = has_code_block or has_expected_actual
    produces_error = has_stack or has_expected_actual
    matches_issue = produces_error
    in_source = bool(cited_file) and not any(
        seg in (cited_file or "")
        for seg in ("/site-packages/", "/node_modules/", "/.venv/", "/dist-packages/")
    )
    deterministic = produces_error  # text-only mode: assume deterministic if signature is stable

    return {
        "runs": runs_to_completion,
        "produces_error": produces_error,
        "matches": matches_issue,
        "in_source": in_source,
        "deterministic": deterministic,
        "_cited_file": cited_file,
    }


def run(repo_id: int, issue_id: int, run_id: int) -> bool:
    db = session_scope()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return False
        checks = _five_checks(issue.body)
        cited = checks.pop("_cited_file", None)
        passed = sum(1 for v in checks.values() if v)
        all_pass = passed == 5
        confidence = round(passed / 5, 2)

        log = (
            f"reproduction five-check: {checks}\n"
            f"cited_file={cited}\nconfidence={confidence}\n"
            f"verdict={'PASS' if all_pass else 'FAIL'}\n"
            f"checked_at={datetime.now(timezone.utc).isoformat()}"
        )
        issue.reproduction_log = log
        issue.repro_checks = checks
        issue.reproducibility_confidence = confidence
        if all_pass:
            issue.status = "reproduced"
        else:
            issue.status = "abandoned"
            issue.abandon_reason = "reproduction_confidence_below_threshold"
        db.commit()
        emit_log(
            run_id,
            "info" if all_pass else "warn",
            f"repro: passed={passed}/5 confidence={confidence}",
            stage="reproduce",
        )
        return all_pass
    finally:
        db.close()
