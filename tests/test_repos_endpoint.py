"""Integration: POST /repos with mocked GitHub responses."""

from __future__ import annotations

from unittest.mock import patch


_UPSTREAM = {
    "name": "react", "full_name": "facebook/react", "default_branch": "main",
    "language": "javascript", "stargazers_count": 200000, "archived": False,
    "fork": False,
}
_FORK = {
    "name": "react", "full_name": "myname/react", "default_branch": "main",
    "fork": True, "parent": {"full_name": "facebook/react"},
}


def _gh_get_repo(self, full):
    if full.lower() == "facebook/react":
        return _UPSTREAM
    if full.lower() == "myname/react":
        return _FORK
    raise RuntimeError(f"unmocked: {full}")


def test_post_repos_creates(client):
    with patch("app.services.github_client.GitHubClient.get_repo", _gh_get_repo):
        r = client.post(
            "/api/v1/repos",
            json={
                "upstream_url": "https://github.com/facebook/react",
                "fork_url": "https://github.com/myname/react",
            },
        )
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["upstream"]["owner"] == "facebook"
    assert j["fork"]["owner"] == "myname"
    assert j["language"] == "javascript"
    assert j.get("run_id")


def test_post_repos_rejects_non_fork(client):
    bad_fork = {**_FORK, "parent": {"full_name": "other/react"}}

    def _gh(self, full):
        if full == "facebook/react":
            return _UPSTREAM
        return bad_fork

    with patch("app.services.github_client.GitHubClient.get_repo", _gh):
        r = client.post(
            "/api/v1/repos",
            json={"upstream_url": "https://github.com/facebook/react",
                  "fork_url": "https://github.com/myname/react"},
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "fork_not_of_upstream"


def test_post_repos_rejects_bad_url(client):
    r = client.post("/api/v1/repos",
                    json={"upstream_url": "not a url", "fork_url": "github.com/x/y"})
    assert r.status_code == 422


def test_post_repos_duplicate(client):
    with patch("app.services.github_client.GitHubClient.get_repo", _gh_get_repo):
        client.post("/api/v1/repos",
                    json={"upstream_url": "https://github.com/facebook/react",
                          "fork_url": "https://github.com/myname/react"})
        r = client.post("/api/v1/repos",
                        json={"upstream_url": "https://github.com/facebook/react",
                              "fork_url": "https://github.com/myname/react"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "repo_already_exists"


def test_pause_resume(client):
    with patch("app.services.github_client.GitHubClient.get_repo", _gh_get_repo):
        r = client.post("/api/v1/repos",
                        json={"upstream_url": "https://github.com/facebook/react",
                              "fork_url": "https://github.com/myname/react"})
    rid = r.json()["id"]

    rp = client.post(f"/api/v1/repos/{rid}/pause", json={"reason": "manual"})
    assert rp.status_code == 200
    assert rp.json()["paused"] is True
    rr = client.post(f"/api/v1/repos/{rid}/resume")
    assert rr.json()["paused"] is False


def test_settings_pat_invalid(client, monkeypatch):
    from app.services.github_client import GitHubError

    def bad(self):
        raise GitHubError("pat_invalid", "nope", status=400)

    monkeypatch.setattr("app.services.github_client.GitHubClient.get_authenticated_user", bad)
    r = client.put("/api/v1/settings/pat", json={"github_pat": "garbage"})
    assert r.status_code == 400
