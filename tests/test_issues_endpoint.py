"""/issues endpoints."""

from __future__ import annotations

from app.db.models import Issue, Repository, User
from app.db.session import session_scope


def _seed():
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = Repository(
            user_id=u.id, upstream_url="https://github.com/x/y",
            upstream_owner="x", upstream_name="y",
            fork_url="https://github.com/me/y", fork_owner="me", fork_name="y",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        i = Issue(repo_id=repo.id, github_number=1, title="bug", body="Steps...",
                  labels=["bug"], score=80, eligibility_verdict="eligible", status="detected")
        s.add(i)
        s.commit()
        s.refresh(i)
        return repo.id, i.id
    finally:
        s.close()


def test_list_issues(client):
    repo_id, _ = _seed()
    r = client.get(f"/api/v1/repos/{repo_id}/issues")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_get_issue(client):
    _, iid = _seed()
    r = client.get(f"/api/v1/issues/{iid}")
    assert r.status_code == 200
    assert r.json()["title"] == "bug"


def test_skip_issue(client):
    _, iid = _seed()
    r = client.post(f"/api/v1/issues/{iid}/skip", json={"reason": "user"})
    assert r.json()["status"] == "skipped"


def test_no_brainers_empty(client):
    repo_id, _ = _seed()
    r = client.get(f"/api/v1/repos/{repo_id}/no-brainers")
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
