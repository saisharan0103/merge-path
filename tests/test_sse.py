"""SSE smoke test — replay-on-connect on a terminal run."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import LogEvent, PipelineRun, Repository, User
from app.db.session import session_scope


def test_sse_replays_logs_on_terminal_run(client):
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
        run = PipelineRun(
            repo_id=repo.id, kind="onboarding", status="succeeded",
            finished_at=datetime.now(timezone.utc),
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        for i in range(3):
            s.add(LogEvent(run_id=run.id, level="info", stage="fetch_metadata",
                           message=f"event {i}"))
        s.commit()
        run_id = run.id
    finally:
        s.close()

    with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as resp:
        body = b""
        for chunk in resp.iter_bytes():
            body += chunk
            if b"event: end" in body:
                break

    text = body.decode("utf-8", errors="replace")
    # 3 log events should have been replayed
    assert text.count("event: log") == 3
    assert "event: end" in text


def test_sse_404_when_missing(client):
    r = client.get("/api/v1/runs/999999/stream")
    assert r.status_code == 404
