from __future__ import annotations

from app.db.models import FixPlan, Issue, Patch
from app.services.pr_writer import _deterministic, validate_pr


def test_validate_pr_pass():
    body = (
        "## What changed\n\nFix.\n\n"
        "## Why\n\nRoot cause.\n\n"
        "## How tested\n\n- Existing tests: passed\n\nFixes #1\n"
    )
    ok, reason = validate_pr("fix: empty input crash", body, 1)
    assert ok, reason


def test_validate_pr_too_long_title():
    ok, reason = validate_pr("x" * 80, "## What changed\n\n## Why\n\n## How tested\n\nFixes #1\n", 1)
    assert not ok and reason == "title_length"


def test_validate_pr_missing_sections():
    ok, reason = validate_pr("fix: x", "no sections", 1)
    assert not ok


def test_validate_pr_hype_word():
    body = (
        "## What changed\n\n## Why\n\n## How tested\n\nFixes #1\n"
    )
    ok, reason = validate_pr("amazing fix for crash", body, 1)
    assert not ok and reason == "title_hype"


def test_deterministic_template_emits_required_sections():
    issue = Issue(repo_id=1, github_number=42, title="empty input crashes", body="x")
    plan = FixPlan(issue_id=1, root_cause="empty list", approach="add guard", target_files=["app/p.py"])
    patch = Patch(issue_id=1, files_modified=["app/p.py"], loc_added=3, loc_removed=0)
    title, body = _deterministic("fix(<scope>): <desc>", issue, plan, patch, "pytest")
    assert title.startswith("fix:")
    assert "## What changed" in body
    assert "Fixes #42" in body
