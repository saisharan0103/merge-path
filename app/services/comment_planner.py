"""Issue comment generator + poster.

In fake mode the codex runner returns a deterministic comment; we still apply
all the validation rules from `prompts/03_issue_comment.md` (≤100 words, no
banned phrases, must reference file:function).
"""

from __future__ import annotations

import re

from app.config import settings
from app.db.models import (
    FixPlan,
    Issue,
    IssueComment,
    PullRequest,
    Repository,
    User,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.services.codex_runner import CodexInvocation, CodexRunner
from app.services.github_client import GitHubClient, GitHubError

_BANNED_PHRASES = ("Can I", "may I", "Hi ", "Thanks ", "TODO", "TBD")


def validate_comment(text: str) -> tuple[bool, str | None]:
    if not text or not text.strip():
        return False, "empty"
    words = text.split()
    if len(words) > 100:
        return False, "too_long"
    for ph in _BANNED_PHRASES:
        if ph.lower() in text.lower():
            return False, f"banned:{ph.strip()}"
    if text.count("?") > 2:
        return False, "too_many_questions"
    if not re.search(r"`[^`]+\.[a-z]+(?::[a-z_]+)?`", text):
        return False, "no_file_function_ref"
    return True, None


def _build_prompt(issue: Issue, fp: FixPlan | None, branch: str | None) -> str:
    target_first = (fp.target_files or ["app/file.py"])[0] if fp else "app/file.py"
    target_func = (fp.target_functions or ["function"])[0] if fp and fp.target_functions else "function"
    return (
        "Write a maintainer-style issue comment.\n"
        f"Issue: #{issue.github_number} {issue.title}\n"
        f"Reproduction confirmed.\n"
        f"Target: `{target_first}:{target_func}`\n"
        f"Branch: {branch or 'patchpilot/...' }\n"
    )


def run(repo_id: int, issue_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return
        # idempotency: skip if already posted
        existing = (
            db.query(IssueComment)
            .filter(IssueComment.issue_id == issue.id, IssueComment.status == "posted")
            .first()
        )
        if existing:
            emit_log(run_id, "info", "comment already posted; skipping", stage="post_comment")
            return

        if (issue.reproducibility_confidence or 0) < 0.7:
            emit_log(run_id, "info", "skipping comment: low confidence", stage="post_comment")
            return

        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            return
        fp = db.query(FixPlan).filter(FixPlan.issue_id == issue.id).order_by(FixPlan.id.desc()).first()
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.repo_id == repo.id, PullRequest.issue_id == issue.id)
            .first()
        )
        prompt = _build_prompt(issue, fp, pr.fork_branch_name if pr else None)

        cwd = settings.repos_dir / str(repo_id)
        cwd.mkdir(parents=True, exist_ok=True)
        runner = CodexRunner()

        text: str | None = None
        for attempt in range(2):
            res = runner.invoke(
                CodexInvocation(
                    cwd=str(cwd),
                    prompt=prompt,
                    files_in_scope=[],
                    max_loc=0,
                    output_target="comment.md",
                    timeout_seconds=120,
                )
            )
            candidate = (res.output_text or "").strip()
            ok, reason = validate_comment(candidate)
            if ok:
                text = candidate
                break
            emit_log(run_id, "warn", f"comment attempt {attempt+1} invalid: {reason}", stage="post_comment")

        c = IssueComment(
            issue_id=issue.id,
            drafted_text=text,
            confidence=issue.reproducibility_confidence,
        )
        db.add(c)
        if text:
            user = db.query(User).filter(User.id == repo.user_id).first()
            try:
                gh = GitHubClient.for_user(user)
                resp = gh.create_issue_comment(
                    f"{repo.upstream_owner}/{repo.upstream_name}", issue.github_number, text
                )
                c.posted_text = text
                c.status = "posted"
                c.posted_url = resp.get("html_url")
                c.github_comment_id = resp.get("id")
            except GitHubError as exc:
                emit_log(run_id, "warn", f"comment post failed: {exc.code}", stage="post_comment")
                c.status = "skipped"
        else:
            c.status = "skipped"
        db.commit()
    finally:
        db.close()
