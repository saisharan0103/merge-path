from urllib.parse import urlparse


def normalize_repo_url(repo_url: str) -> str:
    return repo_url.strip().rstrip("/")


def derive_owner_name(repo_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(repo_url)
    path = parsed.path if parsed.scheme else repo_url
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None, None
    return parts[-2], parts[-1].removesuffix(".git")
