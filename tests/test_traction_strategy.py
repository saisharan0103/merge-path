"""Exercise traction polling + strategy adapter against mocked GitHub."""

from __future__ import annotations

from app.db.models import PRTraction, PullRequest, RepoStrategy, Repository, User
from app.db.session import session_scope
from app.pipeline.traction_worker import poll_traction_sync
from app.services.strategy_adapter import update_for_repo
from app.services.traction_scorer import update_for_pr
from tests.fixtures import patch_github


def _seed_repo_with_pr(merged: bool = False):
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = Repository(
            user_id=u.id, upstream_url="https://github.com/demoorg/demo",
            upstream_owner="demoorg", upstream_name="demo",
            fork_url="https://github.com/myname/demo", fork_owner="myname", fork_name="demo",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        pr = PullRequest(
            repo_id=repo.id, type="issue_fix", upstream_pr_number=42, status="open",
            fork_branch_name="patchpilot/issue-1", upstream_url="https://github.com/x/y/pull/42",
        )
        s.add(pr)
        s.commit()
        s.refresh(pr)
        return repo.id, pr.id
    finally:
        s.close()


def test_update_for_pr(tmp_env, monkeypatch):
    patch_github(monkeypatch)
    repo_id, pr_id = _seed_repo_with_pr()
    update_for_pr(pr_id)

    s = session_scope()
    try:
        rows = s.query(PRTraction).filter(PRTraction.pr_id == pr_id).all()
        assert len(rows) == 1
        assert rows[0].verdict in ("pending", "neutral", "positive", "negative")
    finally:
        s.close()


def test_strategy_adapter(tmp_env, monkeypatch):
    patch_github(monkeypatch)
    repo_id, pr_id = _seed_repo_with_pr()
    update_for_pr(pr_id)
    update_for_repo(repo_id)
    s = session_scope()
    try:
        st = s.query(RepoStrategy).filter(RepoStrategy.repo_id == repo_id).first()
        assert st is not None
        assert st.current_verdict in ("green", "yellow", "red", "blacklist")
    finally:
        s.close()


def test_poll_traction_aggregate(tmp_env, monkeypatch):
    patch_github(monkeypatch)
    _seed_repo_with_pr()
    out = poll_traction_sync()
    assert out["prs"] >= 1
