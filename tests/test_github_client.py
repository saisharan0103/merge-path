"""GitHubClient: error mapping + retry behaviour with httpx mock."""

from __future__ import annotations

import httpx
import pytest

from app.services.github_client import GitHubClient, GitHubError


def _client_with_handler(handler) -> GitHubClient:
    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client(base_url="https://api.github.com", transport=transport, timeout=2.0)
    return GitHubClient(pat="testpat", client=httpx_client, max_retries=1)


def test_pat_invalid_on_401():
    def h(req):
        return httpx.Response(401, json={"message": "bad creds"})
    with pytest.raises(GitHubError) as ei:
        _client_with_handler(h).get_authenticated_user()
    assert ei.value.code == "pat_invalid"


def test_404_repo_not_found():
    def h(req):
        return httpx.Response(404, json={"message": "not found"})
    with pytest.raises(GitHubError) as ei:
        _client_with_handler(h).get_repo("a/b")
    assert ei.value.code == "repo_not_found"


def test_500_retried_then_raises():
    counter = {"n": 0}

    def h(req):
        counter["n"] += 1
        return httpx.Response(503, json={"message": "down"})
    with pytest.raises(GitHubError) as ei:
        _client_with_handler(h).get_repo("a/b")
    assert ei.value.code == "upstream_5xx"
    assert counter["n"] >= 2  # retried at least once


def test_get_repo_success_returns_body():
    def h(req):
        return httpx.Response(200, json={"name": "react", "fork": False})
    body = _client_with_handler(h).get_repo("facebook/react")
    assert body["name"] == "react"


def test_get_readme_decodes_base64():
    import base64
    encoded = base64.b64encode(b"# hello").decode()

    def h(req):
        return httpx.Response(200, json={"encoding": "base64", "content": encoded})
    body = _client_with_handler(h).get_readme("facebook/react")
    assert body == "# hello"
