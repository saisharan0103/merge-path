"""Subprocess runner with timeout — used for tests, lint, install, etc."""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


def run(command: str, *, cwd: str | Path, timeout: int = 600) -> CommandResult:
    start = time.time()
    try:
        proc = subprocess.run(
            shlex.split(command, posix=True),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            exit_code=124,
            stdout=(exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            duration_seconds=time.time() - start,
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            command=command,
            exit_code=127,
            stdout="",
            stderr=str(exc),
            duration_seconds=time.time() - start,
        )
    return CommandResult(
        command=command,
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[:50_000],
        stderr=(proc.stderr or "")[:50_000],
        duration_seconds=time.time() - start,
    )
