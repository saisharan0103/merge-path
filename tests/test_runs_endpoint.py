"""/runs endpoints + log endpoints."""

from __future__ import annotations

from app.db.models import LogEvent, PipelineRun, Repository, User
from app.db.session import session_scope


def _seed_run():
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
        run = PipelineRun(repo_id=repo.id, kind="onboarding", status="running")
        s.add(run)
        s.commit()
        s.refresh(run)
        s.add(LogEvent(run_id=run.id, level="info", stage="fetch_metadata", message="hi"))
        s.commit()
        return run.id
    finally:
        s.close()


def test_runs_list(client):
    _seed_run()
    r = client.get("/api/v1/runs")
    j = r.json()
    assert j["total"] == 1


def test_run_detail(client):
    rid = _seed_run()
    r = client.get(f"/api/v1/runs/{rid}")
    j = r.json()
    assert j["id"] == rid
    assert j["log_count"] == 1


def test_run_logs(client):
    rid = _seed_run()
    r = client.get(f"/api/v1/runs/{rid}/logs")
    j = r.json()
    assert j["total"] == 1
    assert j["items"][0]["message"] == "hi"


def test_run_stop(client):
    rid = _seed_run()
    r = client.post(f"/api/v1/runs/{rid}/stop")
    assert r.status_code == 200
    assert r.json()["cancel_requested"] is True


def test_activity_feed(client):
    _seed_run()
    r = client.get("/api/v1/activity")
    assert r.status_code == 200
    assert r.json()["total"] == 1
