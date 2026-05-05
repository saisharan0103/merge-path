"""Capture PNG screenshots of every UI page using playwright."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "UI_SCREENSHOTS"
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("dashboard", "/"),
    ("repos", "/repos"),
    ("repo_detail_overview", "/repos/1"),
    ("scores", "/scores"),
    ("issues", "/issues"),
    ("issue_detail", "/issues/1"),
    ("prs", "/prs"),
    ("pr_detail", "/prs/1"),
    ("strategy", "/strategy"),
    ("activity", "/activity"),
    ("settings", "/settings"),
    ("run_detail", "/runs/1"),
]


def main(base: str = "http://localhost:3000") -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        for name, path in PAGES:
            url = f"{base}{path}"
            try:
                page.goto(url, wait_until="networkidle", timeout=20_000)
                # give React Query a moment to fetch + render
                page.wait_for_timeout(1500)
                target = OUT / f"{name}.png"
                page.screenshot(path=str(target), full_page=True)
                print(f"{name:30s} {path:20s} -> {target.name}")
            except Exception as exc:
                print(f"FAILED {name} {path}: {exc}", file=sys.stderr)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
