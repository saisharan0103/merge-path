from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.health_scorer import _score


def test_alive_high():
    s, v = _score({
        "last_commit_at": datetime.now(timezone.utc) - timedelta(days=2),
        "merged_pr_count_30d": 12,
        "release_count_180d": 5,
        "ci_pass_rate": 0.95,
        "external_merge_rate": 0.5,
        "median_review_hours": 18,
    })
    assert v == "alive"
    assert s >= 60


def test_stale_low():
    s, v = _score({
        "last_commit_at": datetime.now(timezone.utc) - timedelta(days=400),
        "merged_pr_count_30d": 0,
        "release_count_180d": 0,
        "ci_pass_rate": None,
        "external_merge_rate": None,
        "median_review_hours": None,
    })
    assert v == "stale"
    assert s < 30


def test_handles_nulls():
    s, v = _score({})
    assert s == 0
    assert v == "stale"
