"""Git operations — clone fork, sync upstream, branch, push.

In tests / fake mode (no network) we work entirely on a local-only git
repo created by `CodexRunner` so the patch flow can still produce a real
diff and a `pull_requests` row.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.db.models import (
    Issue,
    NoBrainerOpportunity,
    Patch,
    PullRequest,
    Repository,
    User,
)
from app.db.session import session_scope
from app.log_bus import emit_log
from app.utils.crypto import decrypt
from app.utils.redis_client import repo_lock
from app.utils.slug import slugify


def _git(cwd: str | Path, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    if shutil.which("git") is None:
        return 127, "", "git not installed"
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env
    )
    return proc.returncode, proc.stdout, proc.stderr


def ensure_clone(repo: Repository, *, pat: str | None = None) -> Path:
    """Idempotent: clone fork if needed, ensure upstream remote, fetch."""
    target = settings.repos_dir / str(repo.id)
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        if shutil.which("git") is None:
            # offline: init local only
            _git(target, "init", "-q")
            _git(target, "config", "user.email", "patchpilot@local")
            _git(target, "config", "user.name", "PatchPilot")
            (target / "README.md").write_text("# placeholder\n")
            _git(target, "add", "-A")
            _git(target, "commit", "-q", "-m", "init")
            return target
        clone_url = repo.fork_url
        if pat:
            # Inject token for HTTPS clone
            clone_url = clone_url.replace("https://", f"https://x-access-token:{pat}@")
        rc, _, err = _git(Path.cwd(), "clone", "--depth", "1", clone_url, str(target))
        if rc != 0:
            # fall back to upstream
            rc2, _, _ = _git(Path.cwd(), "clone", "--depth", "1", repo.upstream_url, str(target))
            if rc2 != 0:
                # finally: init local
                _git(target, "init", "-q")
                _git(target, "config", "user.email", "patchpilot@local")
                _git(target, "config", "user.name", "PatchPilot")
                (target / "README.md").write_text("# placeholder\n")
                _git(target, "add", "-A")
                _git(target, "commit", "-q", "-m", "init")
                return target
    # ensure upstream remote
    rc, out, _ = _git(target, "remote")
    remotes = set(out.split())
    if "upstream" not in remotes and shutil.which("git"):
        _git(target, "remote", "add", "upstream", repo.upstream_url)
    return target


def _branch_for_issue(issue: Issue) -> str:
    return f"patchpilot/issue-{issue.github_number}-{slugify(issue.title or 'fix')}"


def _branch_for_no_brainer(nb: NoBrainerOpportunity) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    type_slug = (nb.type or "docs").replace("_", "-")
    return f"patchpilot/no-brainer-{type_slug}-{ts}"


def _commit_and_push(target: Path, branch: str, message: str, push: bool, run_id: int) -> str | None:
    """Returns the commit SHA (or None on failure)."""
    _git(target, "checkout", "-B", branch)
    _git(target, "add", "-A")
    rc, _, _ = _git(target, "diff", "--cached", "--quiet")
    if rc == 0:
        # no changes staged; nothing to commit
        emit_log(run_id, "warn", "no changes to commit", stage="push_branch")
        return None
    rc, _, err = _git(target, "-c", "user.email=patchpilot@local",
                      "-c", "user.name=PatchPilot",
                      "commit", "-m", message)
    if rc != 0:
        emit_log(run_id, "warn", f"commit failed: {err[:200]}", stage="push_branch")
        return None
    rc, sha, _ = _git(target, "rev-parse", "HEAD")
    sha = sha.strip()
    if push and shutil.which("git"):
        rc, _, err = _git(target, "push", "-u", "origin", branch, "--force-with-lease")
        if rc != 0:
            emit_log(run_id, "warn", f"push failed (continuing locally): {err[:200]}", stage="push_branch")
    return sha or None


def push_for_issue(repo_id: int, issue_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        user = db.query(User).filter(User.id == repo.user_id).first() if repo else None
        if not repo or not issue:
            return

        pat: str | None = None
        if user and user.github_pat_encrypted:
            try:
                pat = decrypt(user.github_pat_encrypted)
            except Exception:
                pat = None
        elif settings.github_token:
            pat = settings.github_token

        with repo_lock(repo_id):
            target = ensure_clone(repo, pat=pat)
            branch = _branch_for_issue(issue)
            commit_msg = f"fix: address #{issue.github_number} - {issue.title}\n\nCloses #{issue.github_number}"
            sha = _commit_and_push(target, branch, commit_msg, push=bool(pat), run_id=run_id)

        # Persist PR row scaffold (PR not yet opened — pr_writer handles that)
        patch = (
            db.query(Patch)
            .filter(Patch.issue_id == issue_id)
            .order_by(Patch.id.desc())
            .first()
        )
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.repo_id == repo.id, PullRequest.issue_id == issue.id)
            .first()
        )
        if pr is None:
            pr = PullRequest(
                repo_id=repo.id,
                issue_id=issue.id,
                patch_id=patch.id if patch else None,
                type="issue_fix",
                fork_branch_name=branch,
                fork_branch_sha=sha,
                upstream_base_branch=repo.upstream_default_branch,
                files_changed_count=len(patch.files_modified or []) if patch else 0,
                loc_added=patch.loc_added if patch else 0,
                loc_removed=patch.loc_removed if patch else 0,
                status="draft",
            )
            db.add(pr)
        else:
            pr.fork_branch_name = branch
            pr.fork_branch_sha = sha or pr.fork_branch_sha
        db.commit()
        emit_log(run_id, "info", f"pushed branch {branch}", stage="push_branch")
    finally:
        db.close()


def push_for_no_brainer(repo_id: int, nb_id: int, run_id: int) -> None:
    db = session_scope()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        nb = db.query(NoBrainerOpportunity).filter(NoBrainerOpportunity.id == nb_id).first()
        user = db.query(User).filter(User.id == repo.user_id).first() if repo else None
        if not repo or not nb:
            return
        pat: str | None = None
        if user and user.github_pat_encrypted:
            try:
                pat = decrypt(user.github_pat_encrypted)
            except Exception:
                pat = None
        elif settings.github_token:
            pat = settings.github_token

        with repo_lock(repo_id):
            target = ensure_clone(repo, pat=pat)
            branch = _branch_for_no_brainer(nb)
            commit_msg = f"docs({nb.type}): {nb.summary}\n"
            sha = _commit_and_push(target, branch, commit_msg, push=bool(pat), run_id=run_id)

        patch = db.query(Patch).filter(Patch.no_brainer_id == nb.id).order_by(Patch.id.desc()).first()
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.repo_id == repo.id, PullRequest.no_brainer_id == nb.id)
            .first()
        )
        if pr is None:
            pr = PullRequest(
                repo_id=repo.id,
                no_brainer_id=nb.id,
                patch_id=patch.id if patch else None,
                type="no_brainer",
                fork_branch_name=branch,
                fork_branch_sha=sha,
                upstream_base_branch=repo.upstream_default_branch,
                status="draft",
            )
            db.add(pr)
        else:
            pr.fork_branch_name = branch
            pr.fork_branch_sha = sha or pr.fork_branch_sha
        db.commit()
        emit_log(run_id, "info", f"pushed branch {branch}", stage="push_branch")
    finally:
        db.close()
