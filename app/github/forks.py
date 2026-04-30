class ForkClient:
    def ensure_fork(self, repo: str) -> str:
        raise NotImplementedError("Fork creation will be implemented in a later step.")

    def push_branch(self, repo: str, branch: str) -> None:
        raise NotImplementedError("Branch push will be implemented in a later step.")
