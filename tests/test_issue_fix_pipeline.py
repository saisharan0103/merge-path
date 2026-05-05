"""Run the full issue_fix pipeline against mocks + fake codex."""

from __future__ import annotations

from app.db.models import (
    FixPlan,
    Issue,
    IssueComment,
    Patch,
    PipelineRun,
    PullRequest,
    Repository,
    RepositoryProfile,
    User,
)
from app.db.session import session_scope
from app.pipeline.orchestrator import run_pipeline_sync
from tests.fixtures import OPEN_ISSUES, patch_github


def _seed():
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = Repository(
            user_id=u.id,
            upstream_url="https://github.com/demoorg/demo",
            upstream_owner="demoorg",
            upstream_name="demo",
            fork_url="https://github.com/myname/demo",
            fork_owner="myname",
            fork_name="demo",
            health_score=80,
            health_verdict="alive",
        )
        s.add(repo)
        s.commit()
        s.refresh(repo)
        prof = RepositoryProfile(
            repo_id=repo.id,
            primary_language="python",
            tech_stack=["python"],
            test_commands=["pytest -x"],
            run_commands=[], install_commands=[], lint_commands=["ruff check ."],
            build_commands=[], prerequisites=[],
            raw_readme="readme",
        )
        s.add(prof)
        bug = OPEN_ISSUES[0]
        issue = Issue(
            repo_id=repo.id,
            github_number=bug["number"],
            title=bug["title"],
            body=bug["body"],
            labels=["bug"],
            github_state="open",
            github_url=bug["html_url"],
            score=80,
            score_breakdown={"reproducible": 30},
            eligibility_verdict="eligible",
            status="detected",
        )
        s.add(issue)
        s.commit()
        s.refresh(issue)
        run = PipelineRun(
            repo_id=repo.id, issue_id=issue.id, kind="issue_fix", status="pending"
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        return repo.id, issue.id, run.id
    finally:
        s.close()


def test_full_issue_fix(tmp_env, monkeypatch):
    patch_github(monkeypatch)
    repo_id, issue_id, run_id = _seed()

    run_pipeline_sync(run_id)

    s = session_scope()
    try:
        run = s.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        assert run.status in ("succeeded",), (
            f"unexpected: status={run.status} stage={run.stage} "
            f"abandon={run.abandon_reason} err={run.error}"
        )
        plan = s.query(FixPlan).filter(FixPlan.issue_id == issue_id).first()
        assert plan is not None
        assert plan.target_files
        patch = s.query(Patch).filter(Patch.issue_id == issue_id).first()
        assert patch is not None
        assert patch.diff_text
        pr = s.query(PullRequest).filter(PullRequest.issue_id == issue_id).first()
        assert pr is not None
        assert pr.title
        assert pr.body
        assert "Fixes #" in (pr.body or "")
        assert pr.upstream_pr_number == 4242
        # comment was attempted
        comment = s.query(IssueComment).filter(IssueComment.issue_id == issue_id).first()
        assert comment is not None
    finally:
        s.close()
