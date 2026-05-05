from __future__ import annotations

from app.services.strategy_adapter import _classify


def test_no_prs():
    v, _, na = _classify(0, 0)
    assert v == "yellow"


def test_green():
    v, _, na = _classify(10, 2)
    assert v == "green"
    assert na == "escalate_to_issues"


def test_yellow():
    v, _, _ = _classify(2, 2)
    assert v == "yellow"


def test_red():
    v, _, _ = _classify(0, 1)
    assert v == "red"


def test_blacklist():
    v, _, _ = _classify(-10, 2)
    assert v == "blacklist"
