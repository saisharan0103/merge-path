"""Branch + filename slug helpers."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str, max_words: int = 6, max_chars: int = 40) -> str:
    """Lowercase, alphanum + dashes only, first N words, max chars.

    Used to derive the `{slug}` portion of `patchpilot/issue-{n}-{slug}`.
    """
    if not text:
        return "x"
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    if not words:
        return "x"
    joined = "-".join(words[:max_words])
    return joined[:max_chars].rstrip("-") or "x"
