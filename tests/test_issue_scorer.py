from __future__ import annotations

from app.services.issue_scorer import _score_issue


def _make(**over):
    base = {
        "title": "Empty input crashes parser",
        "body": (
            "## Steps to reproduce\n```python\nparse('')\n```\n"
            "Expected: clean exit\n"
            "Actual: ValueError\n"
            "Traceback (most recent call last):\n  File \"app/parser.py\", line 12\n"
            * 2  # bulk it up
        ),
        "labels": [{"name": "bug"}],
        "comments": 2,
        "created_at": "2026-04-30T00:00:00Z",
        "state": "open",
    }
    base.update(over)
    return base


def test_eligible_high_score():
    score, breakdown, filt = _score_issue(_make(), merged_recently=True)
    assert filt is None
    assert score >= 60
    assert "reproducible" in breakdown


def test_filtered_when_ui_label():
    out = _score_issue(_make(labels=[{"name": "ui"}], body="this is a CSS layout bug on mobile"),
                       merged_recently=False)
    assert out[2] == "ui_or_visual"


def test_filtered_banned_label():
    out = _score_issue(_make(labels=[{"name": "wontfix"}]), merged_recently=False)
    assert out[2] == "banned_label"


def test_filtered_thin_body():
    out = _score_issue(_make(body="too short"), merged_recently=False)
    assert out[2] == "body_too_thin"


def test_filtered_paid_service():
    body = "needs aws credentials and a stripe key to reproduce, see steps to reproduce. " * 5
    out = _score_issue(_make(body=body), merged_recently=False)
    assert out[2] == "needs_paid_service"
