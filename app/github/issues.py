from fastapi import HTTPException

from app.github.client import GitHubClient


class IssueClient:
    def __init__(self, github: GitHubClient | None = None) -> None:
        self.github = github or GitHubClient()

    def list_repo_issues(
        self,
        owner: str,
        repo: str,
        max_items: int = 100,
    ) -> list[dict[str, object]]:
        if not self.github.token:
            raise HTTPException(status_code=400, detail="GITHUB_TOKEN is required to fetch issues")

        issues: list[dict[str, object]] = []
        page = 1
        per_page = min(max(max_items, 1), 100)
        with self.github.client() as client:
            while len(issues) < max_items:
                response = client.get(
                    f"/repos/{owner}/{repo}/issues",
                    params={"state": "all", "per_page": per_page, "page": page},
                )
                if response.status_code == 404:
                    raise HTTPException(status_code=404, detail="GitHub repository not found")
                if response.status_code == 401:
                    raise HTTPException(status_code=401, detail="GitHub token is invalid or unauthorized")
                if response.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"GitHub issue fetch failed: {response.text}")

                batch = response.json()
                if not batch:
                    break
                issues.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
        return issues[:max_items]
