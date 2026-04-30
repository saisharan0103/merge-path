import httpx

from app.core.config import settings


class GitHubClient:
    """Thin GitHub REST client wrapper."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="https://api.github.com", headers=self._headers(), timeout=30.0)
