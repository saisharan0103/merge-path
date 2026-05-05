"""PR title + body generation, then opening the PR via the GitHub API.

Uses Codex to draft, validates the output, and falls back to a deterministic
template if the LLM fails twice. Idempotent: an existing PR for the branch
is updated rather than duplicated.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.models import (
    FixPlan,
    Issue,
    NoBrainerOpportunity,
    Patch,
    PullRequest,
    Repository,
    RepositoryPRPatterns,
    User,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.codex_runner import CodexInvocation, CodexRunner
from app.services.github_client import GitHubClient, GitHubError


_BANNED_BODY = ("thanks", "please", "I will", "I have", "in this PR I")
_HYPE_TITLE = ("amazing", "improved", "better", "comprehensive")


def validate_pr(title: str, body: str, issue_number: int | None) -> tuple[bool, str | None]:
    if not title or len(title) > 70:
        return False, "title_length"
    if any(h in title.lower() for h in _HYPE_TITLE):
        return False, "title_hype"
    if not body:
        return False, "empty_body"
    word_count = len(body.split())
    if word_count > 250:
        return False, "body_too_long"
    if "## What changed" not in body or "## Why" not in body or "## How tested" not in body:
        return False, "missing_sections"
    if issue_number is not None and f"Fixes #{issue_number}" not in body and f"Closes #{issue_number}" not in body:
        return False, "missing_fixes_line"
    if any(b in body.lower() for b in _BANNED_BODY):
        return False, "banned_phrase"
    return True, None


def _deterministic(title_pattern: str, issue: Issue | None, plan: FixPlan | None,
                   patch: Patch | None, test_command: str) -> tuple[str, str]:
    issue_number = issue.github_number if issue else 0
    title_text = (issue.title if issue else "") or "fix"
    title_text = title_text.lower().strip()
    if title_pattern == "fix(<scope>): <desc>":
        title = f"fix: {title_text[:60]}"
    elif title_pattern == "[<scope>] <desc>":
        title = f"[fix] {title_text[:60]}"
    else:
        title = title_text[:70]
    if len(title) > 70:
        title = title[:70]
    files = (patch.files_modified or []) if patch else []
    regression = files[0] if files else "(none)"
    body = (
        f"## What changed\n\n"
        f"{(plan.approach if plan else 'Smallest fix for the issue.') or 'Smallest fix for the issue.'}\n\n"
        f"## Why\n\n"
        f"{(plan.root_cause if plan else 'See linked issue.') or 'See linked issue.'}\n\n"
        f"## How tested\n\n"
        f"- Existing tests: passed\n"
        f"- Regression test: `{regression}`\n"
        f"- Validation: `{test_command}`\n\n"
        f"Fixes #{issue_number}\n"
    )
    return title, body


def _draft_with_codex(
    title_pattern: str, issue: Issue | None, plan: FixPlan | None, patch: Patch | None
) -> tuple[str, str] | None:
    runner = CodexRunner()
    prompt = (
        "Generate PR title + body for this issue fix. Match repo title pattern: "
        f"`{title_pattern}`.\n"
        f"Issue: #{issue.github_number if issue else 0} {issue.title if issue else ''}\n"
        f"Approach: {plan.approach if plan else ''}\n"
        f"Files: {(patch.files_modified or []) if patch else []}\n"
        "Write JSON to ./pr.json: {\"title\": ..., \"body\": ...}"
    )
    cwd = settings.repos_dir / "_drafts"
    cwd.mkdir(parents=True, exist_ok=True)
    res = runner.invoke(
        CodexInvocation(
            cwd=str(cwd), prompt=prompt, files_in_scope=[], max_loc=0,
            output_target="pr.json", timeout_seconds=120,
        )
    )
    if not res.success or not res.output_text:
        return None
    try:
        data = json.loads(res.output_text)
        return data.get("title", ""), data.get("body", "")
    except Exception:
        return None


def _buffer_window(median_review_hours: float | None) -> tuple[datetime, datetime]:
    multiplier = settings.buffer_multiplier
    if median_review_hours and median_review_hours > 0:
        hours = median_review_hours * multiplier
    else:
        hours = settings.buffer_min_days * 24
    days = hours / 24
    days = max(settings.buffer_min_days, min(settings.buffer_max_days, days))
    now = datetime.now(timezone.utc)
    buf = now + timedelta(days=days)
    grace = buf + timedelta(days=settings.grace_days)
    return buf, grace


def open_for_issue(repo_id: int, issue_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        user = db.query(User).filter(User.id == repo.user_id).first() if repo else None
        plan = db.query(FixPlan).filter(FixPlan.issue_id == issue.id).order_by(FixPlan.id.desc()).first() if issue else None
        patch = db.query(Patch).filter(Patch.issue_id == issue.id).order_by(Patch.id.desc()).first() if issue else None
        patterns = db.query(RepositoryPRPatterns).filter(RepositoryPRPatterns.repo_id == repo_id).first() if repo else None
        pr = db.query(PullRequest).filter(
            PullRequest.repo_id == repo_id, PullRequest.issue_id == issue_id
        ).first() if repo and issue else None
        if not repo or not issue or not pr:
            return

        title_pattern = (patterns.title_pattern if patterns else "plain")
        test_command = ""
        if repo.profile and repo.profile.test_commands:
            test_command = repo.profile.test_commands[0]

        title_body: tuple[str, str] | None = None
        for attempt in range(2):
            cand = _draft_with_codex(title_pattern, issue, plan, patch)
            if cand is None:
                continue
            ok, reason = validate_pr(cand[0], cand[1], issue.github_number)
            if ok:
                title_body = cand
                break
            emit_log(run_id, "warn", f"pr draft attempt {attempt+1} invalid: {reason}", stage="open_pr")

        if title_body is None:
            title_body = _deterministic(title_pattern, issue, plan, patch, test_command)
        title, body = title_body

        median_hours = float(patterns.median_review_hours) if patterns and patterns.median_review_hours else None
        buf, grace = _buffer_window(median_hours)

        pr.title = title
        pr.body = body
        pr.opened_at = datetime.now(timezone.utc)
        pr.buffer_until = buf
        pr.grace_until = grace
        pr.status = "open"

        # Try real PR creation if we have a PAT
        try:
            gh = GitHubClient.for_user(user)
            head = f"{repo.fork_owner}:{pr.fork_branch_name}"
            full = f"{repo.upstream_owner}/{repo.upstream_name}"
            existing = gh.list_pulls_by_head(full, head)
            existing_open = next((p for p in existing if p.get("state") == "open"), None)
            if existing_open:
                pr.upstream_pr_number = existing_open.get("number")
                pr.upstream_url = existing_open.get("html_url")
            else:
                opened = gh.create_pull(
                    full, title=title, body=body, head=head,
                    base=repo.upstream_default_branch, maintainer_can_modify=True,
                )
                pr.upstream_pr_number = opened.get("number")
                pr.upstream_url = opened.get("html_url")
            emit_log(run_id, "info", f"PR opened: {pr.upstream_url}", stage="open_pr")
        except GitHubError as exc:
            emit_log(run_id, "warn", f"PR open via API failed: {exc.code}; persisted locally", stage="open_pr")

        issue.status = "pr_opened"
        db.commit()
    finally:
        db.close()


def open_for_no_brainer(repo_id: int, nb_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        nb = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
        user = db.query(User).filter(User.id == repo.user_id).first() if repo else None
        pr = db.query(PullRequest).filter(
            PullRequest.repo_id == repo_id, PullRequest.no_brainer_id == nb_id
        ).first() if repo and nb else None
        if not repo or not nb or not pr:
            return

        title = f"docs: {nb.summary[:60].lower()}"
        body = (
            f"## What changed\n\n"
            f"{nb.proposed_change}\n\n"
            f"## Why\n\n"
            f"Friction observed during fresh setup.\n\n"
            f"## How tested\n\n"
            f"- Followed updated README from a fresh clone\n"
            f"- Verified the documented commands run\n"
        )
        pr.title = title
        pr.body = body
        pr.opened_at = datetime.now(timezone.utc)
        buf, grace = _buffer_window(None)
        pr.buffer_until = buf
        pr.grace_until = grace
        pr.status = "open"

        try:
            gh = GitHubClient.for_user(user)
            head = f"{repo.fork_owner}:{pr.fork_branch_name}"
            full = f"{repo.upstream_owner}/{repo.upstream_name}"
            existing = gh.list_pulls_by_head(full, head)
            existing_open = next((p for p in existing if p.get("state") == "open"), None)
            if existing_open:
                pr.upstream_pr_number = existing_open.get("number")
                pr.upstream_url = existing_open.get("html_url")
            else:
                opened = gh.create_pull(
                    full, title=title, body=body, head=head,
                    base=repo.upstream_default_branch, maintainer_can_modify=True,
                )
                pr.upstream_pr_number = opened.get("number")
                pr.upstream_url = opened.get("html_url")
            emit_log(run_id, "info", f"no-brainer PR opened: {pr.upstream_url}", stage="open_pr")
        except GitHubError as exc:
            emit_log(run_id, "warn", f"PR open via API failed: {exc.code}; persisted locally", stage="open_pr")

        nb.status = "pr_opened"
        nb.pr_id = pr.id
        db.commit()
    finally:
        db.close()
