from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class CodexRunResult:
    success: bool
    output: str


class CodexRunner:
    def run(self, repo_path: Path, prompt: str) -> CodexRunResult:
        return CodexRunResult(
            success=False,
            output=f"{settings.codex_cli_path} runner is not implemented yet for {repo_path}.",
        )
