"""Detect stack of a checked-out repo on disk."""

from __future__ import annotations

from pathlib import Path

_MARKERS: dict[str, list[str]] = {
    "javascript": ["package.json"],
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java-maven": ["pom.xml"],
    "java-gradle": ["build.gradle", "build.gradle.kts"],
}


def detect(root: Path) -> str:
    """Return the primary stack name; tie-broken by file count."""
    counts: dict[str, int] = {}
    for stack, files in _MARKERS.items():
        n = sum(1 for f in files if (root / f).exists())
        if n:
            counts[stack] = n
    if not counts:
        return "other"
    if "javascript" in counts and (root / "tsconfig.json").exists():
        return "typescript"
    return max(counts, key=counts.get)
