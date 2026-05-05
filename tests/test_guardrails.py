from __future__ import annotations

from app.db.models import Patch
from app.services.guardrails import _file_is_blocked, check_patch


def test_blocked_files():
    assert _file_is_blocked("package-lock.json")
    assert _file_is_blocked("Cargo.lock")
    assert _file_is_blocked(".github/workflows/test.yml")
    assert not _file_is_blocked("src/app.py")


def _patch(**kw):
    p = Patch(
        diff_text=kw.get("diff", "+x\n-y\n"),
        files_modified=kw.get("modified", ["src/app.py"]),
        files_added=kw.get("added", []),
        files_deleted=kw.get("deleted", []),
        loc_added=kw.get("loc_added", 5),
        loc_removed=kw.get("loc_removed", 2),
    )
    return p


def test_pass_case():
    ok, reason = check_patch(_patch(), max_files=5, max_loc=200)
    assert ok and reason is None


def test_empty_diff_rejected():
    ok, reason = check_patch(_patch(diff=""), max_files=5, max_loc=200)
    assert not ok and reason == "empty_diff"


def test_blocked_file_rejected():
    ok, reason = check_patch(_patch(modified=["package-lock.json"]), max_files=5, max_loc=200)
    assert not ok and reason == "blocked_file"


def test_loc_exceeded():
    ok, reason = check_patch(_patch(loc_added=200, loc_removed=200), max_files=5, max_loc=100)
    assert not ok and reason == "loc_exceeded"


def test_too_many_files():
    ok, reason = check_patch(_patch(modified=[f"f{i}.py" for i in range(10)]), max_files=5, max_loc=200)
    assert not ok and reason == "too_many_files"
