from __future__ import annotations

from app.services.pr_pattern_analyzer import detect_title_pattern


def test_conventional_dominant():
    titles = [f"fix(scope): {i}" for i in range(8)] + ["plain title", "[other] thing"]
    assert detect_title_pattern(titles) == "fix(<scope>): <desc>"


def test_bracket_dominant():
    titles = [f"[parser] thing {i}" for i in range(7)] + ["plain", "another plain"]
    assert detect_title_pattern(titles) == "[<scope>] <desc>"


def test_issue_ref():
    titles = [f"fix something (#{i+1})" for i in range(6)] + ["plain", "another"]
    assert detect_title_pattern(titles) == "<desc> (#issue)"


def test_plain_when_no_dominant():
    titles = ["plain " + str(i) for i in range(10)]
    assert detect_title_pattern(titles) == "plain"


def test_empty():
    assert detect_title_pattern([]) == "plain"
