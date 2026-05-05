"""Run the full onboarding pipeline against a mocked GitHub."""

from __future__ import annotations

from app.db.models import (
    Issue,
    NoBrainerOpportunity,
    PipelineRun,
    Repository,
    RepositoryHealthSignal,
    RepositoryPRPatterns,
    RepositoryProfile,
    RepositoryScan,
)
from app.db.session import session_scope
from app.pipeline.orchestrator import run_pipeline_sync
from tests.fixtures import patch_github


def _seed_repo() -> int:
    s = session_scope()
    try:
        u = s.query(__import__("app.db.models", fromlist=["User"]).User).first()
        repo = Repository(
            user_id=u.id,
            upstream_url="https://github.com/demoorg/demo",
            upstream_owner="demoorg",
            upstream_name="demo",
            fork_url="https://github.com/myname/demo",
            fork_owner="myname",
            fork_name="demo",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        run = PipelineRun(repo_id=repo.id, kind="onboarding", status="pending")
        s.add(run)
        s.commit()
        s.refresh(run)
        return run.id
    finally:
        s.close()


def test_full_onboarding(tmp_env, monkeypatch):
    patch_github(monkeypatch)

    run_id = _seed_repo()
    run_pipeline_sync(run_id)

    s = session_scope()
    try:
        run = s.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        assert run.status == "succeeded", f"run failed: {run.error or run.abandon_reason}"
        repo = s.query(Repository).filter(Repository.id == run.repo_id).first()
        assert repo.health_score is not None
        assert repo.health_verdict in ("alive", "weak", "stale")

        prof = s.query(RepositoryProfile).filter(RepositoryProfile.repo_id == repo.id).first()
        assert prof is not None
        assert prof.primary_language == "python"
        assert "pytest -x" in (prof.test_commands or [])

        scan = s.query(RepositoryScan).filter(RepositoryScan.repo_id == repo.id).first()
        assert scan is not None
        assert (scan.total_files or 0) >= 1

        pat = s.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo.id).first()
        assert pat is not None
        assert pat.sample_size and pat.sample_size > 0

        health = s.query(RepositoryHealthSignal).filter(
            RepositoryHealthSignal.repo_id == repo.id
        ).count()
        assert health >= 1

        nb = s.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.repo_id == repo.id).all()
        assert nb  # at least one detected from heuristics

        issues = s.query(Issue).filter(Issue.repo_id == repo.id).all()
        assert issues  # the mocked open issues should be detected
        eligible = [i for i in issues if i.eligibility_verdict == "eligible"]
        assert eligible  # the well-formed bug should pass scoring
    finally:
        s.close()
