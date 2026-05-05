"""Additional GitHubClient coverage."""

from __future__ import annotations

import httpx
import pytest

from app.services.github_client import GitHubClient, GitHubError


def _make(handler, **kw) -> GitHubClient:
    transport = httpx.MockTransport(handler)
    cl = httpx.Client(base_url="https://api.github.com", transport=transport, timeout=2.0)
    return GitHubClient(pat="t", client=cl, max_retries=kw.get("max_retries", 1))


def test_list_open_issues_filters_pulls():
    def h(req):
        return httpx.Response(200, json=[
            {"number": 1, "title": "real issue"},
            {"number": 2, "title": "PR", "pull_request": {"url": "x"}},
        ])
    out = _make(h).list_open_issues("a/b", max_pages=1)
    assert len(out) == 1
    assert out[0]["number"] == 1


def test_list_merged_prs_keeps_only_merged():
    def h(req):
        return httpx.Response(200, json=[
            {"number": 1, "merged_at": "2026-04-01T00:00:00Z"},
            {"number": 2, "merged_at": None},
        ])
    out = _make(h).list_merged_prs("a/b", count=10)
    assert len(out) == 1


def test_list_releases_returns_list():
    def h(req):
        return httpx.Response(200, json=[{"published_at": "2026-04-01T00:00:00Z"}])
    out = _make(h).list_releases("a/b", count=1)
    assert out


def test_list_workflow_runs_handles_404():
    def h(req):
        return httpx.Response(404, json={"message": "no actions"})
    out = _make(h).list_workflow_runs("a/b", count=1)
    assert out == []


def test_create_issue_comment_returns_body():
    def h(req):
        return httpx.Response(201, json={"id": 7, "html_url": "https://x"})
    body = _make(h).create_issue_comment("a/b", 1, "hi")
    assert body["id"] == 7


def test_create_pull_returns_body():
    def h(req):
        return httpx.Response(201, json={"number": 100, "html_url": "https://x"})
    body = _make(h).create_pull(
        "a/b", title="t", body="b", head="me:branch", base="main", maintainer_can_modify=True
    )
    assert body["number"] == 100


def test_list_pulls_by_head():
    def h(req):
        return httpx.Response(200, json=[{"number": 1}])
    out = _make(h).list_pulls_by_head("a/b", "me:branch")
    assert out and out[0]["number"] == 1


def test_get_file_decodes_content():
    import base64
    encoded = base64.b64encode(b"hello").decode()

    def h(req):
        return httpx.Response(200, json={"encoding": "base64", "content": encoded})
    out = _make(h).get_file("a/b", "README.md")
    assert out == "hello"


def test_get_file_returns_none_on_404():
    def h(req):
        return httpx.Response(404)
    out = _make(h).get_file("a/b", "missing.md")
    assert out is None


def test_get_pull_returns_body():
    def h(req):
        return httpx.Response(200, json={"merged": True})
    out = _make(h).get_pull("a/b", 1)
    assert out["merged"] is True


def test_list_pull_comments_empty():
    def h(req):
        return httpx.Response(200, json=[])
    assert _make(h).list_pull_comments("a/b", 1) == []


def test_list_pull_reviews_returns_list():
    def h(req):
        return httpx.Response(200, json=[{"state": "APPROVED"}])
    out = _make(h).list_pull_reviews("a/b", 1)
    assert out[0]["state"] == "APPROVED"


def test_open_pulls_count_uses_link_header():
    def h(req):
        return httpx.Response(
            200, json=[{"id": 1}],
            headers={"link": '<https://api.github.com/repos/a/b/pulls?page=12>; rel="last"'},
        )
    n = _make(h).list_open_pulls_count("a/b")
    assert n == 12
