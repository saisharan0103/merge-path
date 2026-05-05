"""GitHub client wrapper.

We use httpx + raw REST instead of PyGithub directly so we have full control
over rate-limit handling, retries, and offline mocking. (PyGithub stays in
the dep list per spec; if a future feature wants it, it can import here.)

The client centralises:
  - PAT resolution (DB encrypted PAT > env GITHUB_TOKEN > anonymous)
  - Exponential backoff on 5xx + transient errors
  - Wait-until-reset on primary rate limit
  - Translation of HTTP status into our canonical error codes
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.db.models import User
from app.utils.crypto import decrypt
from app.utils.logging import get_logger

_log = get_logger(__name__)

_BASE = "https://api.github.com"
_UA = f"PatchPilot/{settings.app_version}"


class GitHubError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


@dataclass
class _Resp:
    status: int
    body: Any
    headers: dict[str, str]


class GitHubClient:
    """Synchronous GitHub REST wrapper.

    Use ``GitHubClient.for_user(user)`` from request handlers — this resolves
    the PAT (DB > env). For anonymous calls, instantiate with no args.
    """

    def __init__(
        self,
        pat: str | None = None,
        *,
        max_retries: int = 3,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.pat = pat
        self.max_retries = max_retries
        self.timeout = timeout
        self._client = client

    # -- factories --------------------------------------------------------

    @classmethod
    def for_user(cls, user: User | None) -> "GitHubClient":
        pat: str | None = None
        if user and user.github_pat_encrypted:
            try:
                pat = decrypt(user.github_pat_encrypted)
            except Exception as exc:  # pragma: no cover
                _log.warning("PAT decrypt failed: %s", exc)
        if not pat and settings.github_token:
            pat = settings.github_token
        return cls(pat=pat)

    # -- low level --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": _UA,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.pat:
            headers["Authorization"] = f"Bearer {self.pat}"
        return headers

    def _client_or_new(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(base_url=_BASE, timeout=self.timeout)

    def _request(self, method: str, path: str, *, params: dict | None = None, json: Any = None) -> _Resp:
        client = self._client_or_new()
        owns = self._client is None
        backoffs = [2, 8, 30]
        last_exc: Exception | None = None
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    r = client.request(method, path, params=params, json=json, headers=self._headers())
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    last_exc = exc
                    if attempt >= self.max_retries:
                        raise GitHubError("network_error", str(exc), status=502) from exc
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue

                if r.status_code == 401:
                    raise GitHubError("pat_invalid", "GitHub rejected the PAT", status=400)
                if r.status_code == 403:
                    remaining = r.headers.get("X-RateLimit-Remaining")
                    reset = r.headers.get("X-RateLimit-Reset")
                    if remaining == "0" and reset:
                        wait = max(0, int(reset) - int(time.time())) + 2
                        _log.warning("rate-limited; sleeping %ss", wait)
                        time.sleep(min(wait, 60))
                        continue
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        time.sleep(min(int(retry_after) + 5, 60))
                        continue
                    raise GitHubError("forbidden", "GitHub forbidden", status=403)
                if r.status_code == 404:
                    raise GitHubError("repo_not_found", "GitHub returned 404", status=404)
                if r.status_code >= 500:
                    if attempt >= self.max_retries:
                        raise GitHubError("upstream_5xx", f"GitHub {r.status_code}", status=502)
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue

                try:
                    body = r.json() if r.content else None
                except Exception:
                    body = None
                if r.status_code >= 400:
                    msg = (body or {}).get("message") if isinstance(body, dict) else r.text
                    raise GitHubError("github_error", msg or f"HTTP {r.status_code}", status=r.status_code)
                return _Resp(status=r.status_code, body=body, headers=dict(r.headers))
            # exhausted
            raise GitHubError("network_error", str(last_exc) if last_exc else "exhausted", status=502)
        finally:
            if owns:
                client.close()

    # -- high-level helpers -----------------------------------------------

    def get_authenticated_user(self) -> dict[str, Any]:
        return self._request("GET", "/user").body or {}

    def get_repo(self, full_name: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{full_name}").body or {}

    def get_readme(self, full_name: str) -> str | None:
        try:
            r = self._request("GET", f"/repos/{full_name}/readme")
        except GitHubError:
            return None
        if not r.body:
            return None
        if isinstance(r.body, dict) and r.body.get("encoding") == "base64":
            import base64

            try:
                return base64.b64decode(r.body.get("content", "")).decode("utf-8", errors="replace")
            except Exception:
                return None
        return None

    def get_file(self, full_name: str, path: str) -> str | None:
        try:
            r = self._request("GET", f"/repos/{full_name}/contents/{path}")
        except GitHubError:
            return None
        if isinstance(r.body, dict) and r.body.get("encoding") == "base64":
            import base64

            try:
                return base64.b64decode(r.body.get("content", "")).decode("utf-8", errors="replace")
            except Exception:
                return None
        return None

    def list_open_issues(self, full_name: str, *, max_pages: int = 3, per_page: int = 50) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            r = self._request(
                "GET",
                f"/repos/{full_name}/issues",
                params={"state": "open", "per_page": per_page, "page": page},
            )
            items = r.body or []
            # GitHub returns PRs in /issues; filter them out by absence of "pull_request" key
            filtered = [i for i in items if "pull_request" not in i]
            out.extend(filtered)
            if len(items) < per_page:
                break
        return out

    def list_merged_prs(self, full_name: str, *, count: int = 40) -> list[dict[str, Any]]:
        per_page = min(count, 100)
        r = self._request(
            "GET",
            f"/repos/{full_name}/pulls",
            params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": per_page},
        )
        items = r.body or []
        merged = [p for p in items if p.get("merged_at")]
        return merged[:count]

    def list_recent_commits(self, full_name: str, *, count: int = 30) -> list[dict[str, Any]]:
        r = self._request("GET", f"/repos/{full_name}/commits", params={"per_page": min(count, 100)})
        return r.body or []

    def list_releases(self, full_name: str, *, count: int = 30) -> list[dict[str, Any]]:
        r = self._request("GET", f"/repos/{full_name}/releases", params={"per_page": min(count, 100)})
        return r.body or []

    def list_workflow_runs(self, full_name: str, *, count: int = 30) -> list[dict[str, Any]]:
        try:
            r = self._request(
                "GET",
                f"/repos/{full_name}/actions/runs",
                params={"per_page": min(count, 100)},
            )
        except GitHubError:
            return []
        body = r.body if isinstance(r.body, dict) else {}
        return body.get("workflow_runs", []) or []

    def list_open_pulls_count(self, full_name: str) -> int:
        r = self._request(
            "GET", f"/repos/{full_name}/pulls", params={"state": "open", "per_page": 1}
        )
        # we don't get a total directly; fall back to len + Link header parsing
        body = r.body or []
        link = r.headers.get("link") or r.headers.get("Link")
        if link:
            import re

            m = re.search(r'<[^>]*[?&]page=(\d+)[^>]*>; rel="last"', link)
            if m:
                return int(m.group(1))
        return len(body)

    def create_issue_comment(self, full_name: str, issue_number: int, body: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/repos/{full_name}/issues/{issue_number}/comments", json={"body": body}
        ).body or {}

    def create_pull(
        self,
        full_name: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        maintainer_can_modify: bool = True,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{full_name}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "maintainer_can_modify": maintainer_can_modify,
            },
        ).body or {}

    def list_pulls_by_head(self, full_name: str, head: str) -> list[dict[str, Any]]:
        r = self._request("GET", f"/repos/{full_name}/pulls", params={"head": head, "state": "all"})
        return r.body or []

    def get_pull(self, full_name: str, number: int) -> dict[str, Any]:
        return self._request("GET", f"/repos/{full_name}/pulls/{number}").body or {}

    def list_pull_comments(self, full_name: str, number: int) -> list[dict[str, Any]]:
        r = self._request("GET", f"/repos/{full_name}/issues/{number}/comments")
        return r.body or []

    def list_pull_reviews(self, full_name: str, number: int) -> list[dict[str, Any]]:
        r = self._request("GET", f"/repos/{full_name}/pulls/{number}/reviews")
        return r.body or []
