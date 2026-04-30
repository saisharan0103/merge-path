from dataclasses import dataclass


@dataclass
class PullRequestDraft:
    title: str
    body: str
    head: str
    base: str


class PullRequestClient:
    def open_pr(self, repo: str, draft: PullRequestDraft) -> str:
        raise NotImplementedError("PR creation will be implemented in a later step.")
