"""GitHub response fixtures + helpers for tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _now_iso(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


REPO_UPSTREAM = {
    "name": "demo",
    "full_name": "demoorg/demo",
    "default_branch": "main",
    "language": "python",
    "stargazers_count": 1234,
    "archived": False,
    "fork": False,
}

REPO_FORK = {
    "name": "demo",
    "full_name": "myname/demo",
    "default_branch": "main",
    "fork": True,
    "parent": {"full_name": "demoorg/demo"},
}

README_GOOD = """# Demo Project

A small CLI tool.

## Setup

```bash
pip install -e .
```

Configure your `.env` file before running.

## Usage

Run the demo with `demo run`.
"""


def merged_pr(number: int, title: str, *, days_ago: int = 5, files: int = 3, loc: int = 50,
              author: str = "contributor") -> dict:
    return {
        "number": number,
        "title": title,
        "merged_at": _now_iso(days_ago),
        "created_at": _now_iso(days_ago + 1),
        "labels": [{"name": "bug"}],
        "user": {"login": author},
    }


def merged_prs(n: int = 25) -> list[dict]:
    out = []
    for i in range(n):
        if i % 3 == 0:
            t = f"fix(parser): handle case {i}"
        elif i % 3 == 1:
            t = f"[parser] handle case {i}"
        else:
            t = f"plain title {i}"
        out.append(merged_pr(100 + i, t, days_ago=i + 1))
    return out


def pr_files(_number: int) -> list[dict]:
    return [
        {"filename": "src/parser.py", "additions": 12, "deletions": 4},
        {"filename": "tests/test_parser.py", "additions": 30, "deletions": 0},
        {"filename": "README.md", "additions": 5, "deletions": 0},
    ]


def commits() -> list[dict]:
    return [
        {
            "commit": {"committer": {"date": _now_iso(2)}},
            "author": {"login": "maintainer"},
        }
    ]


def releases() -> list[dict]:
    return [
        {"published_at": _now_iso(10)},
        {"published_at": _now_iso(60)},
    ]


def workflow_runs() -> list[dict]:
    return [{"conclusion": "success"}, {"conclusion": "success"}, {"conclusion": "failure"}]


OPEN_ISSUES = [
    {
        "number": 1,
        "title": "Empty input crashes parser",
        "body": (
            "## Steps to reproduce\n```python\nparser.parse('')\n```\n"
            "Expected: clean exit\n"
            "Actual: ValueError\n"
            "Traceback (most recent call last):\n"
            '  File "src/parser.py", line 12, in parse\n'
            "    raise ValueError\n"
        ),
        "labels": [{"name": "bug"}],
        "state": "open",
        "html_url": "https://github.com/demoorg/demo/issues/1",
        "comments": 1,
        "created_at": _now_iso(3),
    },
    {
        "number": 2,
        "title": "Help: how do I use this?",
        "body": "small body",
        "labels": [{"name": "question"}],
        "state": "open",
        "html_url": "https://github.com/demoorg/demo/issues/2",
        "comments": 0,
        "created_at": _now_iso(1),
    },
]


def file_for(path: str) -> str | None:
    if path == "pyproject.toml":
        return "[project]\nname='demo'\n"
    if path == "CONTRIBUTING.md":
        return "Run tests with pytest."
    return None


class MockGitHub:
    """Patch target: replaces GitHubClient methods."""

    def get_repo(self, full_name):
        if "demoorg/demo" in full_name:
            return REPO_UPSTREAM
        if "myname/demo" in full_name:
            return REPO_FORK
        return REPO_UPSTREAM

    def get_authenticated_user(self):
        return {"login": "myname"}

    def get_readme(self, _full):
        return README_GOOD

    def get_file(self, _full, path):
        return file_for(path)

    def list_recent_commits(self, _full, **kw):
        return commits()

    def list_releases(self, _full, **kw):
        return releases()

    def list_workflow_runs(self, _full, **kw):
        return workflow_runs()

    def list_open_pulls_count(self, _full):
        return 2

    def list_merged_prs(self, _full, count=40):
        return merged_prs(count)[:count]

    def list_open_issues(self, _full, **kw):
        return OPEN_ISSUES

    def create_issue_comment(self, _full, _number, body):
        return {"id": 999, "html_url": "https://github.com/demoorg/demo/issues/1#c1"}

    def create_pull(self, _full, **kw):
        return {"number": 4242, "html_url": "https://github.com/demoorg/demo/pull/4242"}

    def list_pulls_by_head(self, _full, _head):
        return []

    def get_pull(self, _full, _n):
        return {"merged": False, "state": "open"}

    def list_pull_comments(self, _full, _n):
        return []

    def list_pull_reviews(self, _full, _n):
        return []

    def _request(self, method, path, **kw):
        # Used by pr_pattern_analyzer for /pulls/<n>/files and code_mapper for /git/trees
        from types import SimpleNamespace
        if "/files" in path:
            return SimpleNamespace(status=200, body=pr_files(0), headers={})
        if "/git/trees/" in path:
            tree = [
                {"path": "src/parser.py", "type": "blob"},
                {"path": "src/__init__.py", "type": "blob"},
                {"path": "tests/test_parser.py", "type": "blob"},
                {"path": "pyproject.toml", "type": "blob"},
                {"path": "README.md", "type": "blob"},
            ]
            return SimpleNamespace(status=200, body={"tree": tree}, headers={})
        return SimpleNamespace(status=200, body=None, headers={})


def patch_github(monkeypatch) -> MockGitHub:
    """Replace every public method on GitHubClient with the mock equivalent."""
    mock = MockGitHub()
    from app.services import github_client as gc

    for name in dir(MockGitHub):
        if name.startswith("_") and name != "_request":
            continue
        if hasattr(gc.GitHubClient, name):
            monkeypatch.setattr(
                gc.GitHubClient, name,
                lambda self, *a, _bound=getattr(mock, name), **kw: _bound(*a, **kw),
            )
    monkeypatch.setattr(gc.GitHubClient, "_request",
                        lambda self, *a, _bound=mock._request, **kw: _bound(*a, **kw))
    return mock
