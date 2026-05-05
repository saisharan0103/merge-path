"""Codex CLI wrapper.

Per `DECISIONS.md`: prefer the official Python SDK (``openai-codex-sdk``);
fall back to subprocess. Behind ``CODEX_FAKE_MODE=true`` we return canned
diffs so tests don't burn real credits.

The SDK package isn't on PyPI for many environments, so we keep the
subprocess path as the working default and treat the SDK as best-effort.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.utils.logging import get_logger

_log = get_logger(__name__)


@dataclass
class CodexInvocation:
    cwd: str
    prompt: str
    files_in_scope: list[str] = field(default_factory=list)
    max_loc: int = 200
    timeout_seconds: int = 600
    output_target: str | None = None  # e.g. "fix_plan.json", "comment.md", "pr.json"


@dataclass
class CodexResult:
    success: bool
    diff: str | None = None
    files_modified: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    output_text: str | None = None  # contents of output_target if any


def _git(cwd: str, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def _safe_diff(cwd: str) -> str:
    rc, out, _ = _git(cwd, "diff", "HEAD")
    return out if rc == 0 else ""


def _parse_diff_files(diff: str) -> tuple[list[str], list[str], list[str]]:
    modified: list[str] = []
    added: list[str] = []
    deleted: list[str] = []
    cur_status = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            cur_status = "modified"
        elif line.startswith("new file"):
            cur_status = "added"
        elif line.startswith("deleted file"):
            cur_status = "deleted"
        elif line.startswith("+++ b/") and cur_status:
            path = line[6:]
            if path == "/dev/null":
                continue
            if cur_status == "added":
                added.append(path)
            elif cur_status == "deleted":
                deleted.append(path)
            else:
                modified.append(path)
            cur_status = None
    return modified, added, deleted


class CodexRunner:
    def __init__(self, *, binary: str | None = None, default_timeout: int | None = None) -> None:
        self.binary = binary or settings.codex_binary
        self.default_timeout = default_timeout or settings.codex_default_timeout
        self.fake = settings.codex_fake_mode

    # -- health -----------------------------------------------------------

    def health_check(self) -> bool:
        if self.fake:
            return True
        if shutil.which(self.binary) is None:
            return False
        try:
            proc = subprocess.run(
                [self.binary, "--version"], capture_output=True, text=True, timeout=5
            )
            return proc.returncode == 0
        except Exception:
            return False

    # -- main -------------------------------------------------------------

    def invoke(self, inv: CodexInvocation) -> CodexResult:
        if self.fake:
            return self._fake(inv)
        return self._invoke_real(inv)

    # -- fake mode --------------------------------------------------------

    def _fake(self, inv: CodexInvocation) -> CodexResult:
        """Return a canned, deterministic result.

        Behaviour:
          - If `output_target` ends with `.json` we drop a minimal plan/pr JSON.
          - If `output_target` ends with `.md` we drop a minimal markdown.
          - Otherwise we modify (or create) `PATCHPILOT_NOTES.md` and stage a
            real `git diff` so downstream code paths can read it.
        """
        cwd = Path(inv.cwd)
        cwd.mkdir(parents=True, exist_ok=True)
        if not (cwd / ".git").exists():
            _git(str(cwd), "init", "-q")
            _git(str(cwd), "config", "user.email", "fake@patchpilot")
            _git(str(cwd), "config", "user.name", "fake")
            (cwd / "README.md").write_text("# fake repo\n")
            _git(str(cwd), "add", "-A")
            _git(str(cwd), "commit", "-q", "-m", "init")

        target = inv.output_target or "PATCHPILOT_NOTES.md"
        path = cwd / target

        content: str
        if target.endswith(".json"):
            if "fix_plan" in target:
                content = (
                    '{"root_cause":"Fake fix plan for testing.",'
                    '"target_files":["README.md"],'
                    '"target_functions":[],'
                    '"approach":"Add a clarifying paragraph.",'
                    '"tests_to_add":[],'
                    '"expected_loc":2,'
                    '"risk_notes":"none",'
                    '"out_of_scope_observations":""}'
                )
            elif "pr" in target:
                content = (
                    '{"title":"docs: clarify setup",'
                    '"body":"## What changed\\n\\nA clarifying paragraph.\\n\\n'
                    '## Why\\n\\nThe README was unclear about setup.\\n\\n'
                    '## How tested\\n\\n- Existing tests: passed\\n- Validation commands: `pytest`\\n\\n'
                    'Fixes #1"}'
                )
            else:
                content = "{}"
        elif target.endswith(".md"):
            content = (
                "I reproduced this on latest main (abcdef0).\n\n"
                "**Repro:** ran the snippet from the issue body.\n"
                "**Expected:** clean exit.\n"
                "**Actual:** exception raised.\n\n"
                "Root cause looks like `parser.py:parse` — empty input not guarded.\n\n"
                "Opening a focused PR with a regression test shortly.\n"
            )
        else:
            content = "fake patch — appended by CodexRunner in fake mode\n"

        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text() if path.exists() else ""
        path.write_text(existing + content if not target.endswith((".json", ".md")) else content)

        # Stage the new file so `git diff --cached` captures it (works for new files).
        _git(str(cwd), "add", "-A")
        rc, diff_cached, _ = _git(str(cwd), "diff", "--cached", "HEAD")
        diff = diff_cached if rc == 0 else _safe_diff(str(cwd))
        modified, added, deleted = _parse_diff_files(diff)
        return CodexResult(
            success=True,
            diff=diff,
            files_modified=modified,
            files_added=added,
            files_deleted=deleted,
            raw_stdout="[fake codex] wrote " + str(path),
            raw_stderr="",
            exit_code=0,
            duration_seconds=0.01,
            output_text=content,
        )

    # -- real subprocess --------------------------------------------------

    def _invoke_real(self, inv: CodexInvocation) -> CodexResult:
        if shutil.which(self.binary) is None:
            return CodexResult(
                success=False,
                error="codex_not_installed",
                exit_code=127,
                raw_stderr=f"{self.binary} not found on PATH",
            )

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(inv.prompt)
            prompt_path = f.name

        cmd = [
            self.binary,
            "exec",
            "--cwd",
            inv.cwd,
            "--prompt-file",
            prompt_path,
            "--non-interactive",
        ]
        for fp in inv.files_in_scope:
            cmd.extend(["--scope", fp])
        if inv.max_loc:
            cmd.extend(["--max-loc", str(inv.max_loc)])

        env = {**os.environ, "CODEX_NONINTERACTIVE": "1"}
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=inv.cwd,
                capture_output=True,
                text=True,
                timeout=inv.timeout_seconds or self.default_timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return CodexResult(
                success=False,
                error="codex_timeout",
                exit_code=124,
                duration_seconds=time.time() - start,
            )
        except Exception as exc:  # pragma: no cover
            return CodexResult(success=False, error=f"codex_exception:{exc}", exit_code=1)
        finally:
            try:
                os.unlink(prompt_path)
            except Exception:
                pass

        diff = _safe_diff(inv.cwd)
        modified, added, deleted = _parse_diff_files(diff)
        output_text = None
        if inv.output_target:
            p = Path(inv.cwd) / inv.output_target
            if p.exists():
                try:
                    output_text = p.read_text(errors="replace")
                except Exception:
                    output_text = None

        return CodexResult(
            success=(proc.returncode == 0),
            diff=diff or None,
            files_modified=modified,
            files_added=added,
            files_deleted=deleted,
            raw_stdout=proc.stdout[:8000],
            raw_stderr=proc.stderr[:8000],
            exit_code=proc.returncode,
            duration_seconds=time.time() - start,
            output_text=output_text,
            error=None if proc.returncode == 0 else f"codex_exit_{proc.returncode}",
        )
