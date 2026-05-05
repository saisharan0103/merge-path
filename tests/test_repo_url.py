"""URL parsing tests."""

from __future__ import annotations

import pytest

from app.utils.repo_url import parse_github_url


@pytest.mark.parametrize(
    "url, owner, name",
    [
        ("https://github.com/facebook/react", "facebook", "react"),
        ("github.com/pallets/click", "pallets", "click"),
        ("https://github.com/golang/go.git", "golang", "go"),
        ("https://github.com/owner/name/", "owner", "name"),
    ],
)
def test_parse_ok(url, owner, name):
    p = parse_github_url(url)
    assert p is not None
    assert p.owner == owner
    assert p.name == name
    assert p.url.startswith("https://github.com/")


@pytest.mark.parametrize(
    "url",
    ["", "not a url", "https://gitlab.com/x/y", "https://github.com/onlyowner"],
)
def test_parse_reject(url):
    assert parse_github_url(url) is None
