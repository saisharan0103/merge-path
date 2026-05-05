"""Exercise /metrics/* endpoints with seeded data."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import (
    Issue,
    PipelineRun,
    PullRequest,
    RepoStrategy,
    Repository,
    User,
)
from app.db.session import session_scope


def _seed_data():
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = Repository(
            user_id=u.id, upstream_url="https://github.com/x/y",
            upstream_owner="x", upstream_name="y",
            fork_url="https://github.com/me/y", fork_owner="me", fork_name="y",
            health_score=80, health_verdict="alive",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        s.add(RepoStrategy(repo_id=repo.id, current_verdict="green", history=[]))
        s.add(Issue(repo_id=repo.id, github_number=1, title="t", body="b",
                    eligibility_verdict="eligible", status="detected",
                    detected_at=datetime.now(timezone.utc)))
        s.add(PullRequest(repo_id=repo.id, type="issue_fix", status="merged",
                          opened_at=datetime.now(timezone.utc),
                          merged_at=datetime.now(timezone.utc),
                          upstream_pr_number=1))
        s.add(PullRequest(repo_id=repo.id, type="issue_fix", status="open",
                          opened_at=datetime.now(timezone.utc),
                          upstream_pr_number=2))
        s.add(PullRequest(repo_id=repo.id, type="issue_fix", status="closed",
                          opened_at=datetime.now(timezone.utc),
                          closed_at=datetime.now(timezone.utc),
                          upstream_pr_number=3))
        s.add(PipelineRun(repo_id=repo.id, kind="onboarding", status="succeeded",
                          finished_at=datetime.now(timezone.utc)))
        s.commit()
    finally:
        s.close()


def test_metrics_overview(client):
    _seed_data()
    r = client.get("/api/v1/metrics/overview")
    j = r.json()
    assert j["total_repos"] == 1
    assert j["total_prs"] == 3
    assert j["merged_prs"] == 1
    assert j["closed_prs"] == 1
    assert j["open_prs"] == 1
    assert 0 < j["merge_rate"] < 1


def test_metrics_timeseries_daily(client):
    _seed_data()
    r = client.get("/api/v1/metrics/timeseries?period=daily&metric=prs_opened")
    j = r.json()
    assert j["period"] == "daily"
    assert isinstance(j["series"], list)


def test_metrics_by_repo(client):
    _seed_data()
    r = client.get("/api/v1/metrics/by-repo")
    items = r.json()["items"]
    assert items
    assert items[0]["prs_opened"] == 3


def test_metrics_funnel(client):
    _seed_data()
    r = client.get("/api/v1/metrics/funnel")
    j = r.json()
    assert j["issues_detected"] >= 1
    assert j["issues_eligible"] >= 1
    assert j["prs_opened"] == 3


def test_strategy_summary(client):
    _seed_data()
    r = client.get("/api/v1/strategy/summary")
    j = r.json()
    assert j["green"] == 1
