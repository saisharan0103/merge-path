from __future__ import annotations

from app.services.traction_scorer import _score_signals


def test_merged_positive():
    s, v = _score_signals(
        comments=2, maintainer_engaged=True, reactions=1,
        changes_requested=False, approved=True, status="merged", radio_silence=False,
    )
    # 3 (engaged) +1 (rxn) +5 (approved) +10 (merged) = 19
    assert s == 19
    assert v == "positive"


def test_closed_negative():
    s, v = _score_signals(
        comments=0, maintainer_engaged=False, reactions=0,
        changes_requested=False, approved=False, status="closed", radio_silence=False,
    )
    assert s == -5 and v == "negative"


def test_pending_zero():
    s, v = _score_signals(
        comments=0, maintainer_engaged=False, reactions=0,
        changes_requested=False, approved=False, status="open", radio_silence=False,
    )
    assert s == 0 and v == "pending"


def test_radio_silence_after_grace():
    s, v = _score_signals(
        comments=0, maintainer_engaged=False, reactions=0,
        changes_requested=False, approved=False, status="open", radio_silence=True,
    )
    assert s == -2 and v == "negative"
