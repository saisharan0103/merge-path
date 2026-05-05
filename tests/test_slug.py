from __future__ import annotations

from app.utils.slug import slugify


def test_basic():
    assert slugify("Fix Empty Input Crash") == "fix-empty-input-crash"


def test_max_words():
    assert slugify("a b c d e f g h", max_words=3) == "a-b-c"


def test_unicode_strip():
    assert slugify("Söme Ünicode") == "some-unicode"


def test_empty():
    assert slugify("") == "x"


def test_max_chars():
    assert len(slugify("a" * 500, max_chars=10)) <= 10
