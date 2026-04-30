from app.github.client import GitHubClient


class IssueClient:
    def __init__(self, github: GitHubClient | None = None) -> None:
        self.github = github or GitHubClient()

    def list_candidate_issues(
        self,
        owner: str,
        repo: str,
        labels: list[str] | None = None,
        max_items: int = 20,
    ) -> list[dict[str, object]]:
        # Recovery mode keeps network behavior conservative; Step 3 will fill this in.
        return []
