# Codex Integration

## Overview

Codex CLI runs as a subprocess. We **do not** call any Codex API directly. The `CodexRunner` service wraps subprocess invocation, handles I/O, parses output, enforces timeouts.

## Why subprocess?

- Codex CLI is opinionated and self-contained
- Sandbox isolation is easier (subprocess + cwd + timeout)
- Easier to swap implementations later (Aider, Claude CLI, etc.) by changing this one module

## Module: `services/codex_runner.py`

### Public interface

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class CodexInvocation:
    cwd: str                       # repo working directory
    prompt: str                    # full prompt content
    files_in_scope: list[str]      # files Codex is allowed to touch
    max_loc: int                   # diff budget
    timeout_seconds: int

@dataclass
class CodexResult:
    success: bool
    diff: Optional[str]            # unified diff text
    files_modified: list[str]
    files_added: list[str]
    files_deleted: list[str]
    raw_stdout: str
    raw_stderr: str
    exit_code: int
    duration_seconds: float
    error: Optional[str]           # if success=False, why

class CodexRunner:
    def __init__(self, codex_binary: str = "codex", default_timeout: int = 600):
        ...

    def invoke(self, inv: CodexInvocation) -> CodexResult:
        """Run Codex CLI in subprocess, capture diff."""
        ...

    def health_check(self) -> bool:
        """Verify codex binary is callable."""
        ...
```

### Invocation pattern

The runner does NOT invoke `codex` interactively. It uses non-interactive mode:

```python
import subprocess, tempfile, os

def invoke(self, inv: CodexInvocation) -> CodexResult:
    # 1. write prompt to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(inv.prompt)
        prompt_path = f.name

    # 2. snapshot git state before
    pre_sha = self._git_rev(inv.cwd)

    # 3. run codex CLI
    cmd = [
        self.binary, "exec",
        "--cwd", inv.cwd,
        "--prompt-file", prompt_path,
        "--non-interactive",
        "--max-loc", str(inv.max_loc),
        # whitelist files codex may modify
        *[arg for f in inv.files_in_scope for arg in ("--scope", f)],
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=inv.cwd,
            capture_output=True,
            text=True,
            timeout=inv.timeout_seconds,
            env={**os.environ, "CODEX_NONINTERACTIVE": "1"},
        )
    except subprocess.TimeoutExpired:
        return CodexResult(success=False, error="codex_timeout", ...)

    # 4. capture diff via git
    diff_text = self._git_diff(inv.cwd, pre_sha)
    files = self._parse_modified_files(diff_text)

    return CodexResult(
        success=(proc.returncode == 0 and diff_text),
        diff=diff_text,
        files_modified=files["modified"],
        files_added=files["added"],
        files_deleted=files["deleted"],
        raw_stdout=proc.stdout,
        raw_stderr=proc.stderr,
        exit_code=proc.returncode,
        duration_seconds=...,
        error=None if proc.returncode == 0 else f"codex_exit_{proc.returncode}",
    )
```

> **Note:** The actual flag set depends on the Codex CLI version installed. The runner abstracts it. If specific flags differ, only `_build_command()` changes — the rest is stable.

## Two Codex tasks

We invoke Codex in **two distinct stages**, with **different prompts**.

### 1. Plan stage (`stages.plan_fix`)
- Goal: produce a structured fix plan (no code yet)
- Prompt: `prompts/01_fix_planner.md`
- Expected output: JSON with fields: `root_cause`, `target_file`, `target_function`, `approach`, `tests_to_add`, `risk_notes`
- Codex CLI is asked to write this plan to `./fix_plan.json` (we parse it back)
- Files in scope: empty (no code changes allowed)

### 2. Patch stage (`stages.generate_patch`)
- Goal: produce the actual code change
- Prompt: `prompts/02_patch_generator.md` with the fix plan injected
- Expected output: edits to source files + new regression test
- Files in scope: limited based on plan + scoring (max N files)
- Diff captured via `git diff`

## Logging

Every Codex invocation is logged to `agent_runs.log`:
- prompt (truncated to 4KB)
- stdout/stderr (truncated to 8KB each)
- exit code, duration
- diff size (LOC count)
- files touched

Sensitive content (PAT, env vars) must be redacted before logging.

## Sandbox

Codex runs inside the repo's clone directory. The clone lives in:
```
$WORKDIR/repos/<repo_id>/<run_id>/
```
After the run (success or fail), the directory is preserved for 24h then garbage collected.

In dev: subprocess only. In prod: same subprocess but inside Docker container with no network for the patch stage (Codex itself may need network for model calls — TBD based on CLI behavior).

## Configuration (env vars)

```
CODEX_BINARY=codex
CODEX_DEFAULT_TIMEOUT=600
CODEX_MAX_LOC_DEFAULT=200
CODEX_WORKDIR=/var/agent/workdir
```

## Failure handling

| Codex result | Action |
|---|---|
| Exit 0, diff present | Pass to validation |
| Exit 0, empty diff | Treat as failure (`error=empty_diff`), retry once with prompt clarification |
| Exit non-zero | Capture stderr, retry once if retry budget remains |
| Timeout | Mark `error=codex_timeout`, retry once with reduced scope |
| Diff exceeds `max_loc` | Mark `error=diff_too_large`, retry with stricter LOC budget |
| Diff touches files outside scope | Mark `error=scope_violation`, retry with explicit file allowlist in prompt |

After all retries, abandon the issue and persist failure in `pipeline_runs.abandon_reason`.

## Health check

On boot, FastAPI calls `CodexRunner.health_check()`:
```python
def health_check(self) -> bool:
    try:
        proc = subprocess.run([self.binary, "--version"], timeout=5, capture_output=True)
        return proc.returncode == 0
    except Exception:
        return False
```

Result surfaces in `/settings` UI.

## Future swap path

To replace Codex with another tool (e.g., Aider), implement the same interface in `aider_runner.py` and swap via env var:
```
CODE_AGENT=codex|aider|claude_cli
```

Pipeline code only depends on the abstract `CodeAgentRunner` interface.
