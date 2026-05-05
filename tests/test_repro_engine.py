from __future__ import annotations

from app.db.models import Issue, Repository, User
from app.db.session import session_scope
from app.services.repro_engine import _five_checks, run as repro_run


def _seed_repo(db, user_id):
    r = Repository(
        user_id=user_id, upstream_url="https://github.com/x/y", upstream_owner="x",
        upstream_name="y", fork_url="https://github.com/me/y", fork_owner="me", fork_name="y",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_five_checks_pass():
    body = (
        "Steps to reproduce:\n"
        "```python\nparse('')\n```\n"
        "Expected: success\n"
        "Actual:\n"
        "Traceback (most recent call last):\n"
        '  File "app/parser.py", line 12, in parse\n'
        "    raise ValueError\n"
    )
    c = _five_checks(body)
    assert c["runs"] is True
    assert c["produces_error"] is True
    assert c["matches"] is True
    assert c["in_source"] is True


def test_five_checks_fail_on_vague():
    body = "This sometimes breaks but I don't know what's wrong."
    c = _five_checks(body)
    assert c["produces_error"] is False


def test_run_marks_abandoned_when_below_threshold(tmp_env):
    s = session_scope()
    try:
        u = s.query(User).first()
        repo = _seed_repo(s, u.id)
        issue = Issue(
            repo_id=repo.id,
            github_number=1,
            title="vague",
            body="I think there's a bug somewhere?",
            status="detected",
        )
        s.add(issue)
        s.commit()
        ok = repro_run(repo.id, issue.id, run_id=999)
        assert ok is False
        s.refresh(issue)
        assert issue.status == "abandoned"
    finally:
        s.close()
