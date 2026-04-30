import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


class RepoManager:
    def clone_or_update(self, repo_url: str) -> Path:
        settings.clone_dir.mkdir(parents=True, exist_ok=True)
        repo_path = settings.clone_dir / self._repo_dir_name(repo_url)
        if repo_path.exists():
            if not (repo_path / ".git").exists():
                raise RuntimeError(f"Local path exists but is not a git repository: {repo_path}")
            self._run_git(["git", "-C", str(repo_path), "fetch", "--all", "--prune"])
            self._run_git(["git", "-C", str(repo_path), "pull", "--ff-only"])
            return repo_path
        self._run_git(["git", "clone", repo_url, str(repo_path)])
        return repo_path

    def _run_git(self, command: list[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise RuntimeError(output or f"Git command failed: {' '.join(command)}")

    @staticmethod
    def _repo_dir_name(repo_url: str) -> str:
        parsed = urlparse(repo_url)
        path = parsed.path if parsed.scheme else repo_url
        parts = [part for part in path.strip("/").removesuffix(".git").split("/") if part]
        if len(parts) >= 2:
            return f"{parts[-2]}-{parts[-1]}"
        return parts[-1] if parts else "repository"
