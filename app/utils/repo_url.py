"""Parse + validate GitHub URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

_GH_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9._-]+)/"
    r"(?P<name>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class ParsedRepo:
    owner: str
    name: str
    url: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_github_url(url: str) -> ParsedRepo | None:
    if not url:
        return None
    m = _GH_RE.match(url.strip())
    if not m:
        return None
    owner = m.group("owner")
    name = m.group("name")
    if name.endswith(".git"):
        name = name[:-4]
    canonical = f"https://github.com/{owner}/{name}"
    return ParsedRepo(owner=owner, name=name, url=canonical)
