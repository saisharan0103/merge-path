"""Code map builder.

For v1 we try to clone the repo (shallow) and walk the file tree. If clone
fails we fall back to GitHub's tree API (truncated for huge repos).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.models import Repository, RepositoryProfile, RepositoryScan, User
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.github_client import GitHubClient
from app.utils.redis_client import repo_lock

_CONFIG_NAMES = {
    "package.json", "tsconfig.json", "pyproject.toml", "setup.py", "setup.cfg",
    "requirements.txt", "Pipfile", "go.mod", "Cargo.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", ".eslintrc.json", ".eslintrc",
    "tox.ini", ".pre-commit-config.yaml", "Makefile",
}

_TEST_PATTERNS = (
    "test_", "tests/", "/test/", "/tests/", "_test.go", ".test.js", ".test.ts",
    ".spec.js", ".spec.ts", "Test.java", "/__tests__/",
)

_ENTRYPOINT_PATTERNS = (
    "src/index.js", "src/index.ts", "src/main.py", "src/main.go",
    "src/main.rs", "main.py", "manage.py", "main.go", "src/main.rs",
    "app/main.py", "cmd/",
)


def _try_clone(repo: Repository, run_id: int) -> Path | None:
    target = settings.repos_dir / str(repo.id)
    target.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        return target
    if shutil.which("git") is None:
        emit_log(run_id, "warn", "git binary not found; skipping clone", stage="build_code_map")
        return None
    cmd = ["git", "clone", "--depth", "1", repo.fork_url, str(target)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except Exception as exc:  # pragma: no cover
        emit_log(run_id, "warn", f"clone failed: {exc}", stage="build_code_map")
        return None
    if proc.returncode != 0:
        emit_log(run_id, "warn", f"clone failed: {proc.stderr[:200]}", stage="build_code_map")
        # try upstream as fallback
        try:
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir(parents=True, exist_ok=True)
            cmd = ["git", "clone", "--depth", "1", repo.upstream_url, str(target)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
            if proc.returncode != 0:
                return None
        except Exception:
            return None
    return target


def _walk(root: Path) -> dict[str, Any]:
    """Return {file_tree, total_files, files} where files is a flat list."""
    file_tree: dict[str, Any] = {}
    total = 0
    flat: list[str] = []
    skip_dirs = {".git", "node_modules", "vendor", "dist", "build", ".next", "target", ".venv", "venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        rel = Path(dirpath).relative_to(root)
        node = file_tree
        for p in rel.parts:
            node = node.setdefault(p, {})
        for fn in filenames:
            node[fn] = None
            total += 1
            flat.append(str((rel / fn).as_posix()))
    return {"file_tree": file_tree, "total_files": total, "files": flat}


def _classify(files: list[str]) -> dict[str, list[str]]:
    config_files = [f for f in files if Path(f).name in _CONFIG_NAMES]
    test_files = [f for f in files if any(p in f for p in _TEST_PATTERNS)]
    entrypoints = [f for f in files if any(p in f for p in _ENTRYPOINT_PATTERNS)]

    src_dirs: set[str] = set()
    for f in files:
        if "/" in f and "test" not in f.lower():
            top = f.split("/", 1)[0]
            if top in {"src", "app", "lib", "internal", "cmd", "pkg"}:
                src_dirs.add(top)
    if not src_dirs:
        src_dirs.add("src")

    return {
        "config_files": sorted(config_files)[:50],
        "test_files": sorted(test_files)[:200],
        "entrypoints": sorted(entrypoints)[:20],
        "source_dirs": sorted(src_dirs),
    }


def _from_github_tree(gh: GitHubClient, repo: Repository) -> dict[str, Any] | None:
    """Fallback when we can't clone: use GitHub's tree API."""
    full = f"{repo.upstream_owner}/{repo.upstream_name}"
    branch = repo.upstream_default_branch or "main"
    try:
        r = gh._request("GET", f"/repos/{full}/git/trees/{branch}", params={"recursive": "1"})
    except Exception:
        return None
    body = r.body or {}
    tree = body.get("tree") or []
    files = [t["path"] for t in tree if t.get("type") == "blob"]
    file_tree: dict[str, Any] = {}
    for f in files:
        node = file_tree
        parts = f.split("/")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = None
    return {"file_tree": file_tree, "total_files": len(files), "files": files}


def build(repo_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        user = db.query(User).filter(User.id == repo.user_id).first()

        with repo_lock(repo_id):
            target = _try_clone(repo, run_id)
            if target:
                tree = _walk(target)
            else:
                gh = GitHubClient.for_user(user)
                tree = _from_github_tree(gh, repo)
                if tree is None:
                    emit_log(run_id, "warn", "no code map: clone+API both failed", stage="build_code_map")
                    return

        cls = _classify(tree["files"])
        existing = db.query(RepositoryScan).filter(RepositoryScan.repo_id == repo.id).first()
        if existing is None:
            existing = RepositoryScan(repo_id=repo.id)
            db.add(existing)
        existing.file_tree = tree["file_tree"]
        existing.total_files = tree["total_files"]
        existing.entrypoints = cls["entrypoints"]
        existing.test_files = cls["test_files"]
        existing.config_files = cls["config_files"]
        existing.source_dirs = cls["source_dirs"]
        db.commit()

        # If profile primary_language is None (rare), persist now from extension counts
        prof = db.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo.id).first()
        if prof and not prof.primary_language:
            prof.primary_language = _guess_lang_from_files(tree["files"])
            db.commit()

        emit_log(
            run_id,
            "info",
            f"code map: files={tree['total_files']} entrypoints={len(cls['entrypoints'])}",
            stage="build_code_map",
        )
    finally:
        db.close()


def _guess_lang_from_files(files: list[str]) -> str:
    counts: dict[str, int] = {}
    for f in files:
        ext = Path(f).suffix.lower()
        counts[ext] = counts.get(ext, 0) + 1
    if counts.get(".py", 0) > 5:
        return "python"
    if counts.get(".ts", 0) + counts.get(".tsx", 0) > 5:
        return "typescript"
    if counts.get(".js", 0) > 5:
        return "javascript"
    if counts.get(".go", 0) > 0:
        return "go"
    if counts.get(".rs", 0) > 0:
        return "rust"
    if counts.get(".java", 0) > 0:
        return "java"
    return "other"
