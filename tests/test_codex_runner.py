from __future__ import annotations

from app.services.codex_runner import CodexInvocation, CodexRunner


def test_health_check_fake_mode(tmp_env):
    assert CodexRunner().health_check() is True


def test_fake_invoke_creates_diff(tmp_env, tmp_path):
    cwd = tmp_path / "repo"
    res = CodexRunner().invoke(
        CodexInvocation(cwd=str(cwd), prompt="do thing", files_in_scope=[], max_loc=80)
    )
    assert res.success
    assert res.diff is not None
    assert res.exit_code == 0


def test_fake_writes_pr_json(tmp_env, tmp_path):
    cwd = tmp_path / "repo"
    res = CodexRunner().invoke(
        CodexInvocation(
            cwd=str(cwd), prompt="generate PR", files_in_scope=[], max_loc=80,
            output_target="pr.json",
        )
    )
    import json
    data = json.loads(res.output_text or "{}")
    assert "title" in data
    assert "body" in data


def test_fake_writes_fix_plan_json(tmp_env, tmp_path):
    cwd = tmp_path / "repo"
    res = CodexRunner().invoke(
        CodexInvocation(
            cwd=str(cwd), prompt="plan", files_in_scope=[], max_loc=80,
            output_target="fix_plan.json",
        )
    )
    import json
    data = json.loads(res.output_text or "{}")
    assert "root_cause" in data
    assert "target_files" in data


def test_fake_writes_comment_md(tmp_env, tmp_path):
    cwd = tmp_path / "repo"
    res = CodexRunner().invoke(
        CodexInvocation(
            cwd=str(cwd), prompt="comment", files_in_scope=[], max_loc=0,
            output_target="comment.md",
        )
    )
    assert res.output_text and "Reproduced" in res.output_text or "reproduced" in res.output_text
