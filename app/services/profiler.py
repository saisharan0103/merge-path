"""Repository profiler.

Reads README + CONTRIBUTING + the package config files for the 5 supported
stacks. Derives:
  - primary_language
  - tech_stack
  - install / test / lint / build / run commands
  - prerequisites (parsed from README headings)
  - summary (first paragraph of README)
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.db.models import Repository, RepositoryProfile, User
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.github_client import GitHubClient


_STACK_FILES = {
    "javascript": ["package.json"],
    "typescript": ["package.json", "tsconfig.json"],
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java-maven": ["pom.xml"],
    "java-gradle": ["build.gradle", "build.gradle.kts"],
}


def _detect_stacks(gh: GitHubClient, full_name: str) -> tuple[str, list[str], dict[str, str]]:
    """Return (primary_language, tech_stack, fetched_files)."""
    fetched: dict[str, str] = {}
    found_stacks: list[str] = []
    for stack, files in _STACK_FILES.items():
        for path in files:
            content = gh.get_file(full_name, path)
            if content is not None:
                fetched[path] = content
                if stack not in found_stacks:
                    found_stacks.append(stack)

    primary: str
    if "package.json" in fetched and "tsconfig.json" in fetched:
        primary = "typescript"
    elif "package.json" in fetched:
        primary = "javascript"
    elif any(p in fetched for p in ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile")):
        primary = "python"
    elif "go.mod" in fetched:
        primary = "go"
    elif "Cargo.toml" in fetched:
        primary = "rust"
    elif "pom.xml" in fetched or "build.gradle" in fetched or "build.gradle.kts" in fetched:
        primary = "java"
    else:
        primary = "other"
    return primary, found_stacks, fetched


def _commands_for(primary: str, files: dict[str, str]) -> dict[str, list[str]]:
    """Return {install, test, lint, build, run}."""
    if primary in {"javascript", "typescript"}:
        scripts: dict[str, str] = {}
        try:
            pj = json.loads(files.get("package.json", "{}"))
            scripts = pj.get("scripts") or {}
        except Exception:
            pj = {}
        # detect package manager via lockfiles isn't available without listing tree; default npm.
        pm = "npm"
        return {
            "install_commands": [f"{pm} install"],
            "test_commands": [f"{pm} test" if scripts.get("test") else f"{pm} test || true"],
            "lint_commands": [f"{pm} run lint"] if scripts.get("lint") else [],
            "build_commands": [f"{pm} run build"] if scripts.get("build") else [],
            "run_commands": [f"{pm} run dev"] if scripts.get("dev") else (
                [f"{pm} start"] if scripts.get("start") else []
            ),
        }
    if primary == "python":
        install = []
        if "pyproject.toml" in files:
            install.append("pip install -e .[dev]")
        if "requirements-dev.txt" in files:
            install.append("pip install -r requirements-dev.txt")
        if "requirements.txt" in files:
            install.append("pip install -r requirements.txt")
        if "Pipfile" in files:
            install.append("pipenv install --dev")
        return {
            "install_commands": install or ["pip install -e ."],
            "test_commands": ["pytest -x"],
            "lint_commands": ["ruff check ."],
            "build_commands": [],
            "run_commands": [],
        }
    if primary == "go":
        return {
            "install_commands": ["go mod download"],
            "test_commands": ["go test ./..."],
            "lint_commands": ["go vet ./..."],
            "build_commands": ["go build ./..."],
            "run_commands": [],
        }
    if primary == "rust":
        return {
            "install_commands": ["cargo fetch"],
            "test_commands": ["cargo test --all"],
            "lint_commands": ["cargo clippy --all-targets -- -D warnings"],
            "build_commands": ["cargo build"],
            "run_commands": [],
        }
    if primary == "java":
        if "pom.xml" in files:
            return {
                "install_commands": ["mvn -B -DskipTests dependency:resolve"],
                "test_commands": ["mvn -B test"],
                "lint_commands": ["mvn -B checkstyle:check"],
                "build_commands": ["mvn -B package -DskipTests"],
                "run_commands": [],
            }
        return {
            "install_commands": ["./gradlew dependencies"],
            "test_commands": ["./gradlew test"],
            "lint_commands": ["./gradlew check"],
            "build_commands": ["./gradlew build -x test"],
            "run_commands": [],
        }
    return {
        "install_commands": [],
        "test_commands": [],
        "lint_commands": [],
        "build_commands": [],
        "run_commands": [],
    }


def _prerequisites(readme: str | None) -> list[str]:
    if not readme:
        return []
    out: list[str] = []
    # naive scan for "Prerequisites" / "Requirements" sections
    sec_re = re.compile(r"^#+\s*(prerequisites|requirements|install)", re.IGNORECASE | re.MULTILINE)
    m = sec_re.search(readme)
    if m:
        tail = readme[m.end():]
        next_h = re.search(r"^#+\s+", tail, re.MULTILINE)
        block = tail[: next_h.start()] if next_h else tail
        for line in block.splitlines():
            line = line.strip()
            if line.startswith(("-", "*")):
                out.append(line.lstrip("-*").strip())
    return out[:10]


def _summary(readme: str | None) -> str | None:
    if not readme:
        return None
    paras = [p.strip() for p in readme.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    if not paras:
        return None
    return paras[0][:600]


def profile(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()
        gh = GitHubClient.for_user(user)
        full = f"{repo.upstream_owner}/{repo.upstream_name}"

        readme = gh.get_readme(full)
        contributing = gh.get_file(full, "CONTRIBUTING.md") or gh.get_file(full, ".github/CONTRIBUTING.md")
        primary, stacks, files = _detect_stacks(gh, full)
        cmds = _commands_for(primary, files)

        existing = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo.id).first()
        if existing is None:
            existing = RepositoryProfile(repo_id=repo.id)
            db.add(existing)
        existing.primary_language = primary
        existing.tech_stack = stacks
        existing.summary = _summary(readme)
        existing.run_commands = cmds["run_commands"]
        existing.test_commands = cmds["test_commands"]
        existing.build_commands = cmds["build_commands"]
        existing.lint_commands = cmds["lint_commands"]
        existing.install_commands = cmds["install_commands"]
        existing.prerequisites = _prerequisites(readme)
        existing.raw_readme = (readme or "")[:50_000]
        existing.contributing_rules = (contributing or "")[:50_000] if contributing else None
        db.commit()

        emit_log(run_id, "info", f"profile: primary={primary} stacks={stacks}", stage="fetch_profile")
    finally:
        db.close()
