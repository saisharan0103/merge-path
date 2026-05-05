from __future__ import annotations

from app.services.comment_planner import validate_comment


def test_pass():
    text = (
        "I reproduced this on main (abcdef0).\n\n"
        "**Repro:** ran the snippet.\n**Expected:** clean exit.\n**Actual:** exception.\n\n"
        "Root cause looks like `parser.py:parse` — empty input not guarded.\n"
    )
    ok, reason = validate_comment(text)
    assert ok, reason


def test_too_long():
    text = ("`f.py:fn` " + "word " * 200)
    ok, reason = validate_comment(text)
    assert not ok and reason == "too_long"


def test_banned_phrase_thanks():
    text = "Thanks for filing this. The issue is at `parser.py:parse`."
    ok, reason = validate_comment(text)
    assert not ok and reason.startswith("banned")


def test_missing_file_function_ref():
    text = "I reproduced it. Expected X, got Y. Root cause is in the parser."
    ok, reason = validate_comment(text)
    assert not ok and reason == "no_file_function_ref"
