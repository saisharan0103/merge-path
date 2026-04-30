import subprocess
from pathlib import Path

from app.core.config import settings


class RepoManager:
    def clone_or_update(self, repo_url: str) -> Path:
        settings.clone_dir.mkdir(parents=True, exist_ok=True)
        repo_path = settings.clone_dir / self._repo_dir_name(repo_url)
        if repo_path.exists():
            return repo_path
        subprocess.run(["git", "clone", repo_url, str(repo_path)], check=True)
        return repo_path

    @staticmethod
    def _repo_dir_name(repo_url: str) -> str:
        return repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
