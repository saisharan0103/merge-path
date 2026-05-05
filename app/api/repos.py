"""Repositories endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import (
    PullRequest,
    Repository,
    RepositoryHealthSignal,
    User,
)
from app.db.session import get_db
from app.pipeline.queue import enqueue_run
from app.schemas.repo import PauseRequest, RepoCreateRequest, RepoDetail, RepoOut, RepoSide
from app.services.github_client import GitHubClient, GitHubError
from app.utils.repo_url import parse_github_url

router = APIRouter()


def _to_side(url: str, owner: str, name: str, default_branch: str | None, verified: bool | None) -> RepoSide:
    return RepoSide(owner=owner, name=name, url=url, default_branch=default_branch, verified=verified)


def _serialize(repo: Repository, db: Session) -> dict:
    open_prs = (
        db.query(PullRequest)
        .filter(PullRequest.repo_id == repo.id, PullRequest.status == "open")
        .count()
    )
    merged_prs = (
        db.query(PullRequest)
        .filter(PullRequest.repo_id == repo.id, PullRequest.status == "merged")
        .count()
    )
    closed_prs = (
        db.query(PullRequest)
        .filter(PullRequest.repo_id == repo.id, PullRequest.status == "closed")
        .count()
    )
    total_terminal = merged_prs + closed_prs
    merge_rate = round(merged_prs / total_terminal, 4) if total_terminal else None
    last_pr = (
        db.query(PullRequest)
        .filter(PullRequest.repo_id == repo.id)
        .order_by(PullRequest.opened_at.desc())
        .first()
    )

    out = RepoOut(
        id=repo.id,
        upstream=_to_side(
            repo.upstream_url, repo.upstream_owner, repo.upstream_name, repo.upstream_default_branch, None
        ),
        fork=_to_side(
            repo.fork_url,
            repo.fork_owner,
            repo.fork_name,
            None,
            repo.fork_verified_at is not None,
        ),
        language=repo.language,
        stars=repo.stars,
        health_score=repo.health_score,
        health_verdict=repo.health_verdict,
        current_phase=repo.current_phase,
        paused=repo.paused,
        pause_reason=repo.pause_reason,
        open_pr_count=open_prs,
        merged_pr_count=merged_prs,
        merge_rate=merge_rate,
        created_at=repo.created_at,
        last_action_at=last_pr.opened_at if last_pr else None,
    )
    return out.model_dump()


@router.post("/repos", status_code=201)
def add_repo(
    body: RepoCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    upstream = parse_github_url(body.upstream_url)
    fork = parse_github_url(body.fork_url)
    if upstream is None or fork is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_failed", "message": "URLs must be github.com/owner/repo"},
        )

    existing = (
        db.query(Repository)
        .filter(
            Repository.user_id == user.id,
            Repository.upstream_owner == upstream.owner,
            Repository.upstream_name == upstream.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "repo_already_exists",
                "message": f"already added: {upstream.full_name}",
                "details": {"id": existing.id},
            },
        )

    gh = GitHubClient.for_user(user)
    try:
        upstream_meta = gh.get_repo(upstream.full_name)
        fork_meta = gh.get_repo(fork.full_name)
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status, detail={"error": exc.code, "message": exc.message}) from None

    parent_full = (fork_meta.get("parent") or {}).get("full_name")
    if parent_full and parent_full.lower() != upstream.full_name.lower():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "fork_not_of_upstream",
                "message": f"fork's parent is {parent_full}, not {upstream.full_name}",
            },
        )
    if parent_full is None and fork_meta.get("fork") is False:
        # offline / mocked clients may set this; still reject when not a fork
        raise HTTPException(
            status_code=400,
            detail={"error": "fork_not_of_upstream", "message": "fork is not a fork"},
        )
    if upstream_meta.get("archived"):
        raise HTTPException(
            status_code=400,
            detail={"error": "repo_archived", "message": "upstream repo is archived"},
        )

    repo = Repository(
        user_id=user.id,
        upstream_url=upstream.url,
        upstream_owner=upstream.owner,
        upstream_name=upstream.name,
        upstream_default_branch=upstream_meta.get("default_branch") or "main",
        fork_url=fork.url,
        fork_owner=fork.owner,
        fork_name=fork.name,
        fork_verified_at=datetime.now(timezone.utc),
        language=upstream_meta.get("language"),
        stars=upstream_meta.get("stargazers_count"),
        current_phase="A_initial",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    run_id = enqueue_run(db, repo_id=repo.id, kind="onboarding")
    db.commit()

    out = _serialize(repo, db)
    out["run_id"] = run_id
    return out


@router.get("/repos")
def list_repos(
    verdict: str | None = None,
    phase: str | None = None,
    paused: bool | None = None,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    q = db.query(Repository).filter(Repository.user_id == user.id)
    if verdict:
        q = q.filter(Repository.health_verdict == verdict)
    if phase:
        q = q.filter(Repository.current_phase == phase)
    if paused is not None:
        q = q.filter(Repository.paused == paused)

    total = q.count()
    if sort:
        col, _, direction = sort.partition(":")
        column = getattr(Repository, col, None)
        if column is not None:
            q = q.order_by(column.desc() if direction == "desc" else column.asc())
    else:
        q = q.order_by(Repository.created_at.desc())

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize(r, db) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/repos/{repo_id}")
def get_repo(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    base = _serialize(repo, db)
    profile = repo.profile
    scan = repo.scan
    pat = repo.pr_patterns
    strat = repo.strategy
    detail = RepoDetail(
        **base,
        profile=_dump(profile, ["summary", "run_commands", "test_commands", "build_commands",
                                "lint_commands", "install_commands", "prerequisites", "tech_stack",
                                "primary_language", "raw_readme", "contributing_rules"]),
        scan=_dump(scan, ["total_files", "entrypoints", "test_files", "config_files",
                          "source_dirs", "file_tree", "scanned_at"]),
        pr_patterns=_dump(pat, ["sample_size", "avg_files_changed", "avg_loc_changed",
                                "pct_with_tests", "pct_with_docs", "common_labels",
                                "title_pattern", "median_review_hours", "test_required",
                                "docs_required", "sample_pr_numbers", "analyzed_at"]),
        strategy=_dump(strat, ["current_verdict", "reason", "next_action", "next_action_at", "history"]),
    )
    return detail.model_dump()


def _dump(obj, fields: list[str]) -> dict | None:
    if obj is None:
        return None
    out = {}
    for f in fields:
        v = getattr(obj, f, None)
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        elif v is not None and not isinstance(v, (str, int, float, bool, list, dict)):
            v = float(v)  # Numeric types
        out[f] = v
    return out


@router.delete("/repos/{repo_id}", status_code=204)
def delete_repo(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    db.delete(repo)
    db.commit()
    return None


@router.post("/repos/{repo_id}/rescan", status_code=202)
def rescan_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    run_id = enqueue_run(db, repo_id=repo.id, kind="rescan")
    db.commit()
    return {"run_id": run_id, "kind": "rescan", "status": "pending"}


@router.post("/repos/{repo_id}/pause")
def pause_repo(
    repo_id: int,
    body: PauseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    repo.paused = True
    repo.pause_reason = body.reason
    db.commit()
    return {"id": repo.id, "paused": True, "pause_reason": body.reason}


@router.post("/repos/{repo_id}/resume")
def resume_repo(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    repo.paused = False
    repo.pause_reason = None
    db.commit()
    return {"id": repo.id, "paused": False}


@router.get("/repos/{repo_id}/health")
def repo_health(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": "repo_not_found", "message": "no such repo"})
    rows = (
        db.query(RepositoryHealthSignal)
        .filter(RepositoryHealthSignal.repo_id == repo.id)
        .order_by(RepositoryHealthSignal.fetched_at.desc())
        .limit(10)
        .all()
    )

    def _row(r: RepositoryHealthSignal) -> dict:
        return {
            "alive_score": r.alive_score,
            "verdict": repo.health_verdict,
            "last_commit_at": r.last_commit_at.isoformat() if r.last_commit_at else None,
            "open_pr_count": r.open_pr_count,
            "merged_pr_count_30d": r.merged_pr_count_30d,
            "median_review_hours": float(r.median_review_hours) if r.median_review_hours is not None else None,
            "maintainer_response_rate": float(r.maintainer_response_rate) if r.maintainer_response_rate is not None else None,
            "release_count_180d": r.release_count_180d,
            "ci_pass_rate": float(r.ci_pass_rate) if r.ci_pass_rate is not None else None,
            "active_contributors_90d": r.active_contributors_90d,
            "external_merge_rate": float(r.external_merge_rate) if r.external_merge_rate is not None else None,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
        }

    history = [_row(r) for r in reversed(rows)]
    current = history[-1] if history else None
    return {"current": current, "history": history}


@router.get("/repos/{repo_id}/profile")
def repo_profile(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo or not repo.profile:
        raise HTTPException(status_code=404, detail={"error": "profile_not_found", "message": "no profile yet"})
    p = repo.profile
    return {
        "summary": p.summary,
        "run_commands": p.run_commands or [],
        "test_commands": p.test_commands or [],
        "build_commands": p.build_commands or [],
        "lint_commands": p.lint_commands or [],
        "install_commands": p.install_commands or [],
        "prerequisites": p.prerequisites or [],
        "tech_stack": p.tech_stack or [],
        "primary_language": p.primary_language,
        "raw_readme": p.raw_readme,
        "contributing_rules": p.contributing_rules,
    }


@router.get("/repos/{repo_id}/scan")
def repo_scan(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo or not repo.scan:
        raise HTTPException(status_code=404, detail={"error": "scan_not_found", "message": "no scan yet"})
    s = repo.scan
    return {
        "total_files": s.total_files,
        "entrypoints": s.entrypoints or [],
        "test_files": s.test_files or [],
        "config_files": s.config_files or [],
        "source_dirs": s.source_dirs or [],
        "file_tree": s.file_tree or {},
        "scanned_at": s.scanned_at.isoformat() if s.scanned_at else None,
    }


@router.get("/repos/{repo_id}/pr-patterns")
def repo_pr_patterns(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo or not repo.pr_patterns:
        raise HTTPException(status_code=404, detail={"error": "patterns_not_found", "message": "no patterns yet"})
    p = repo.pr_patterns
    return {
        "sample_size": p.sample_size,
        "avg_files_changed": float(p.avg_files_changed) if p.avg_files_changed is not None else None,
        "avg_loc_changed": float(p.avg_loc_changed) if p.avg_loc_changed is not None else None,
        "pct_with_tests": float(p.pct_with_tests) if p.pct_with_tests is not None else None,
        "pct_with_docs": float(p.pct_with_docs) if p.pct_with_docs is not None else None,
        "common_labels": p.common_labels or [],
        "title_pattern": p.title_pattern,
        "median_review_hours": float(p.median_review_hours) if p.median_review_hours is not None else None,
        "test_required": p.test_required,
        "docs_required": p.docs_required,
        "sample_pr_numbers": p.sample_pr_numbers or [],
    }


@router.get("/repos/{repo_id}/strategy")
def repo_strategy(repo_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.user_id == user.id).first()
    if not repo or not repo.strategy:
        raise HTTPException(status_code=404, detail={"error": "strategy_not_found", "message": "no strategy yet"})
    s = repo.strategy
    return {
        "current_verdict": s.current_verdict,
        "reason": s.reason,
        "next_action": s.next_action,
        "next_action_at": s.next_action_at.isoformat() if s.next_action_at else None,
        "history": s.history or [],
    }
