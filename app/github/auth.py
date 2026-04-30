from dataclasses import dataclass

from app.core.config import settings


@dataclass
class GitHubAuthState:
    has_token: bool
    has_oauth_config: bool


class GitHubAuth:
    """Local-first GitHub auth helper."""

    def state(self) -> GitHubAuthState:
        return GitHubAuthState(
            has_token=bool(settings.github_token),
            has_oauth_config=bool(settings.github_client_id and settings.github_client_secret),
        )
