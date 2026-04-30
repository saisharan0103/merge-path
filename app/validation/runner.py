from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    success: bool
    command: str
    output: str


class ValidationRunner:
    def run(self, repo_path: Path, commands: list[str]) -> list[ValidationResult]:
        return [
            ValidationResult(success=False, command=command, output="Validation runner is not implemented yet.")
            for command in commands
        ]
