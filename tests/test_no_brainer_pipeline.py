"""Run the full no_brainer_fix pipeline."""

from __future__ import annotations

from app.db.models import (
    NoBrainerOpportunity,
    PipelineRun,
    PullRequest,
    Repository,
    User,
)
from app.db.session import session_scope
from app.pipeline.orchestrator import run_pipeline_sync
from tests.fixtures import patch_github


def _seed():
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = Repository(
            user_id=u.id,
            upstream_url="https://github.com/demoorg/demo",
            upstream_owner="demoorg", upstream_name="demo",
            fork_url="https://github.com/myname/demo",
            fork_owner="myname", fork_name="demo",
            health_score=80, health_verdict="alive",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        nb = NoBrainerOpportunity(
            repo_id=repo.id, type="missing_env_docs", file="README.md",
            summary="missing env docs", proposed_change="add a Configuration section",
            confidence=0.85, status="planned",
        )
        s.add(nb)
        s.commit()
        s.refresh(nb)
        run = PipelineRun(repo_id=repo.id, no_brainer_id=nb.id, kind="no_brainer_fix", status="pending")
        s.add(run)
        s.commit()
        s.refresh(run)
        return repo.id, nb.id, run.id
    finally:
        s.close()


def test_no_brainer_pipeline(tmp_env, monkeypatch):
    patch_github(monkeypatch)
    repo_id, nb_id, run_id = _seed()
    run_pipeline_sync(run_id)

    s = session_scope()
    try:
        run = s.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        assert run.status == "succeeded", (
            f"unexpected: status={run.status} stage={run.stage} "
            f"abandon={run.abandon_reason} err={run.error}"
        )
        nb = s.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
        assert nb.status == "pr_opened"
        pr = s.query(PullRequest).filter(PullRequest.no_brainer_id == nb.id).first()
        assert pr is not None
        assert pr.status == "open"
        assert pr.upstream_pr_number == 4242
    finally:
        s.close()
