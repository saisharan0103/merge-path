"""ORM models — mirrors data/DATA_MODEL.md with SQLite adaptations.

Postgres-isms swapped per DECISIONS.md:
  - JSONB / TEXT[] -> SQLAlchemy JSON (TEXT)
  - BIGSERIAL    -> Integer primary key (autoincrement)
  - ENUM         -> String + CheckConstraint
  - advisory locks -> Redis locks (in services layer)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    github_pat_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    github_username: Mapped[str | None] = mapped_column(String(80))
    git_commit_email: Mapped[str | None] = mapped_column(String(255))
    git_commit_name: Mapped[str | None] = mapped_column(String(120))


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("user_id", "upstream_owner", "upstream_name", name="uq_repo_user_upstream"),
        Index("ix_repositories_user", "user_id"),
        Index("ix_repositories_health_verdict", "health_verdict"),
        Index("ix_repositories_phase", "current_phase"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    upstream_url: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_owner: Mapped[str] = mapped_column(String(120), nullable=False)
    upstream_name: Mapped[str] = mapped_column(String(120), nullable=False)
    upstream_default_branch: Mapped[str] = mapped_column(String(120), default="main")

    fork_url: Mapped[str] = mapped_column(Text, nullable=False)
    fork_owner: Mapped[str] = mapped_column(String(120), nullable=False)
    fork_name: Mapped[str] = mapped_column(String(120), nullable=False)
    fork_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    language: Mapped[str | None] = mapped_column(String(40))
    stars: Mapped[int | None] = mapped_column(Integer)

    health_score: Mapped[int | None] = mapped_column(Integer)
    health_verdict: Mapped[str | None] = mapped_column(String(16))

    current_phase: Mapped[str] = mapped_column(String(24), default="A_initial")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_reason: Mapped[str | None] = mapped_column(Text)

    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    health_signals = relationship(
        "RepositoryHealthSignal", cascade="all, delete-orphan", back_populates="repo"
    )
    profile = relationship(
        "RepositoryProfile", uselist=False, cascade="all, delete-orphan", back_populates="repo"
    )
    scan = relationship(
        "RepositoryScan", uselist=False, cascade="all, delete-orphan", back_populates="repo"
    )
    pr_patterns = relationship(
        "RepositoryPRPatterns", uselist=False, cascade="all, delete-orphan", back_populates="repo"
    )
    strategy = relationship("RepoStrategy", uselist=False, cascade="all, delete-orphan", back_populates="repo")


class RepositoryHealthSignal(Base):
    __tablename__ = "repository_health_signals"
    __table_args__ = (Index("ix_health_repo_time", "repo_id", "fetched_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))

    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open_pr_count: Mapped[int | None] = mapped_column(Integer)
    merged_pr_count_30d: Mapped[int | None] = mapped_column(Integer)
    median_review_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))
    maintainer_response_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    release_count_180d: Mapped[int | None] = mapped_column(Integer)
    ci_pass_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    active_contributors_90d: Mapped[int | None] = mapped_column(Integer)
    external_merge_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))

    alive_score: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[dict | None] = mapped_column(JSON)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repo = relationship("Repository", back_populates="health_signals")


class RepositoryProfile(Base):
    __tablename__ = "repository_profile"

    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[str | None] = mapped_column(Text)
    run_commands: Mapped[list[str] | None] = mapped_column(JSON)
    test_commands: Mapped[list[str] | None] = mapped_column(JSON)
    build_commands: Mapped[list[str] | None] = mapped_column(JSON)
    lint_commands: Mapped[list[str] | None] = mapped_column(JSON)
    install_commands: Mapped[list[str] | None] = mapped_column(JSON)
    prerequisites: Mapped[list[str] | None] = mapped_column(JSON)
    tech_stack: Mapped[list[str] | None] = mapped_column(JSON)
    primary_language: Mapped[str | None] = mapped_column(String(40))
    contributing_rules: Mapped[str | None] = mapped_column(Text)
    raw_readme: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    repo = relationship("Repository", back_populates="profile")


class RepositoryScan(Base):
    __tablename__ = "repository_scan"

    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    file_tree: Mapped[dict | None] = mapped_column(JSON)
    entrypoints: Mapped[list[str] | None] = mapped_column(JSON)
    test_files: Mapped[list[str] | None] = mapped_column(JSON)
    config_files: Mapped[list[str] | None] = mapped_column(JSON)
    source_dirs: Mapped[list[str] | None] = mapped_column(JSON)
    total_files: Mapped[int | None] = mapped_column(Integer)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repo = relationship("Repository", back_populates="scan")


class RepositoryPRPatterns(Base):
    __tablename__ = "repository_pr_patterns"

    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    sample_size: Mapped[int | None] = mapped_column(Integer)
    avg_files_changed: Mapped[float | None] = mapped_column(Numeric(8, 2))
    avg_loc_changed: Mapped[float | None] = mapped_column(Numeric(10, 2))
    pct_with_tests: Mapped[float | None] = mapped_column(Numeric(5, 4))
    pct_with_docs: Mapped[float | None] = mapped_column(Numeric(5, 4))
    common_labels: Mapped[list[str] | None] = mapped_column(JSON)
    title_pattern: Mapped[str | None] = mapped_column(String(80))
    median_review_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sample_pr_numbers: Mapped[list[int] | None] = mapped_column(JSON)
    test_required: Mapped[bool | None] = mapped_column(Boolean)
    docs_required: Mapped[bool | None] = mapped_column(Boolean)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repo = relationship("Repository", back_populates="pr_patterns")


class ContributionRule(Base):
    __tablename__ = "contribution_rules"
    __table_args__ = (
        Index("ix_contrib_rules_lookup", "scope", "repo_id", "issue_id", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    rule_type: Mapped[str | None] = mapped_column(String(40))
    rule_text: Mapped[str | None] = mapped_column(Text)
    rule_value: Mapped[dict | None] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class NoBrainerOpportunity(Base):
    __tablename__ = "no_brainer_opportunities"
    __table_args__ = (Index("ix_nobrainer_repo_status", "repo_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    type: Mapped[str | None] = mapped_column(String(40))
    file: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    proposed_change: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str] = mapped_column(String(20), default="detected")
    pr_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("repo_id", "github_number", name="uq_issue_repo_number"),
        Index("ix_issues_repo_status", "repo_id", "status"),
        Index("ix_issues_score", "score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    github_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[list[str] | None] = mapped_column(JSON)
    github_state: Mapped[str | None] = mapped_column(String(10))
    github_url: Mapped[str | None] = mapped_column(Text)

    score: Mapped[int | None] = mapped_column(Integer)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    eligibility_verdict: Mapped[str | None] = mapped_column(String(20))
    filter_reason: Mapped[str | None] = mapped_column(Text)

    reproducibility_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    reproduction_log: Mapped[str | None] = mapped_column(Text)
    repro_checks: Mapped[dict | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(20), default="detected")
    abandon_reason: Mapped[str | None] = mapped_column(Text)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class FixPlan(Base):
    __tablename__ = "fix_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id"))
    root_cause: Mapped[str | None] = mapped_column(Text)
    target_files: Mapped[list[str] | None] = mapped_column(JSON)
    target_functions: Mapped[list[str] | None] = mapped_column(JSON)
    approach: Mapped[str | None] = mapped_column(Text)
    tests_to_add: Mapped[list[str] | None] = mapped_column(JSON)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), nullable=True)
    no_brainer_id: Mapped[int | None] = mapped_column(ForeignKey("no_brainer_opportunities.id"), nullable=True)
    fix_plan_id: Mapped[int | None] = mapped_column(ForeignKey("fix_plans.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id"))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    diff_text: Mapped[str | None] = mapped_column(Text)
    files_modified: Mapped[list[str] | None] = mapped_column(JSON)
    files_added: Mapped[list[str] | None] = mapped_column(JSON)
    files_deleted: Mapped[list[str] | None] = mapped_column(JSON)
    loc_added: Mapped[int | None] = mapped_column(Integer)
    loc_removed: Mapped[int | None] = mapped_column(Integer)
    codex_stdout: Mapped[str | None] = mapped_column(Text)
    codex_stderr: Mapped[str | None] = mapped_column(Text)
    codex_exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2))
    status: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = (Index("ix_validation_patch", "patch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patch_id: Mapped[int] = mapped_column(ForeignKey("patches.id", ondelete="CASCADE"))
    command: Mapped[str | None] = mapped_column(String(40))
    command_text: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    drafted_text: Mapped[str | None] = mapped_column(Text)
    posted_text: Mapped[str | None] = mapped_column(Text)
    posted_url: Mapped[str | None] = mapped_column(Text)
    github_comment_id: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str | None] = mapped_column(String(20))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        Index("ix_pr_repo_status", "repo_id", "status"),
        Index("ix_pr_buffer", "buffer_until"),
        Index("ix_pr_opened", "opened_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"))
    no_brainer_id: Mapped[int | None] = mapped_column(ForeignKey("no_brainer_opportunities.id"))
    patch_id: Mapped[int | None] = mapped_column(ForeignKey("patches.id"))

    type: Mapped[str | None] = mapped_column(String(20))
    upstream_pr_number: Mapped[int | None] = mapped_column(Integer)
    upstream_url: Mapped[str | None] = mapped_column(Text)
    fork_branch_name: Mapped[str | None] = mapped_column(String(200))
    fork_branch_sha: Mapped[str | None] = mapped_column(String(40))
    upstream_base_branch: Mapped[str | None] = mapped_column(String(120))

    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    files_changed_count: Mapped[int | None] = mapped_column(Integer)
    loc_added: Mapped[int | None] = mapped_column(Integer)
    loc_removed: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str | None] = mapped_column(String(20))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buffer_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PRTraction(Base):
    __tablename__ = "pr_traction"
    __table_args__ = (Index("ix_traction_pr_time", "pr_id", "scored_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"))
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    maintainer_engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    reactions_count: Mapped[int] = mapped_column(Integer, default=0)
    changes_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    traction_score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str | None] = mapped_column(String(12))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RepoStrategy(Base):
    __tablename__ = "repo_strategy"
    __table_args__ = (UniqueConstraint("repo_id", name="uq_strategy_repo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    current_verdict: Mapped[str | None] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(String(40))
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history: Mapped[list[dict] | None] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    repo = relationship("Repository", back_populates="strategy")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','running','paused','succeeded','failed','abandoned','cancelled')",
            name="ck_run_status",
        ),
        Index("ix_run_repo_status", "repo_id", "status"),
        Index("ix_run_status_time", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"))
    no_brainer_id: Mapped[int | None] = mapped_column(ForeignKey("no_brainer_opportunities.id"))

    kind: Mapped[str] = mapped_column(String(20))  # onboarding | issue_fix | no_brainer_fix | rescan
    stage: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="pending")

    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    abandon_reason: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LogEvent(Base):
    __tablename__ = "log_events"
    __table_args__ = (Index("ix_logs_run_time", "run_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    level: Mapped[str | None] = mapped_column(String(8))
    stage: Mapped[str | None] = mapped_column(String(40))
    message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON)


class SettingKV(Base):
    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
