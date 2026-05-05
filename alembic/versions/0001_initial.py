"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("github_pat_encrypted", sa.LargeBinary),
        sa.Column("github_username", sa.String(80)),
        sa.Column("git_commit_email", sa.String(255)),
        sa.Column("git_commit_name", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("upstream_url", sa.Text, nullable=False),
        sa.Column("upstream_owner", sa.String(120), nullable=False),
        sa.Column("upstream_name", sa.String(120), nullable=False),
        sa.Column("upstream_default_branch", sa.String(120), server_default="main"),
        sa.Column("fork_url", sa.Text, nullable=False),
        sa.Column("fork_owner", sa.String(120), nullable=False),
        sa.Column("fork_name", sa.String(120), nullable=False),
        sa.Column("fork_verified_at", sa.DateTime(timezone=True)),
        sa.Column("language", sa.String(40)),
        sa.Column("stars", sa.Integer),
        sa.Column("health_score", sa.Integer),
        sa.Column("health_verdict", sa.String(16)),
        sa.Column("current_phase", sa.String(24), server_default="A_initial"),
        sa.Column("paused", sa.Boolean, server_default=sa.false()),
        sa.Column("pause_reason", sa.Text),
        sa.Column("next_action_at", sa.DateTime(timezone=True)),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "upstream_owner", "upstream_name", name="uq_repo_user_upstream"),
    )
    op.create_index("ix_repositories_user", "repositories", ["user_id"])
    op.create_index("ix_repositories_health_verdict", "repositories", ["health_verdict"])
    op.create_index("ix_repositories_phase", "repositories", ["current_phase"])

    op.create_table(
        "repository_health_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("last_commit_at", sa.DateTime(timezone=True)),
        sa.Column("open_pr_count", sa.Integer),
        sa.Column("merged_pr_count_30d", sa.Integer),
        sa.Column("median_review_hours", sa.Numeric(10, 2)),
        sa.Column("maintainer_response_rate", sa.Numeric(5, 4)),
        sa.Column("release_count_180d", sa.Integer),
        sa.Column("ci_pass_rate", sa.Numeric(5, 4)),
        sa.Column("active_contributors_90d", sa.Integer),
        sa.Column("external_merge_rate", sa.Numeric(5, 4)),
        sa.Column("alive_score", sa.Integer),
        sa.Column("raw", sa.JSON),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_health_repo_time", "repository_health_signals", ["repo_id", "fetched_at"])

    op.create_table(
        "repository_profile",
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("summary", sa.Text),
        sa.Column("run_commands", sa.JSON),
        sa.Column("test_commands", sa.JSON),
        sa.Column("build_commands", sa.JSON),
        sa.Column("lint_commands", sa.JSON),
        sa.Column("install_commands", sa.JSON),
        sa.Column("prerequisites", sa.JSON),
        sa.Column("tech_stack", sa.JSON),
        sa.Column("primary_language", sa.String(40)),
        sa.Column("contributing_rules", sa.Text),
        sa.Column("raw_readme", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "repository_scan",
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("file_tree", sa.JSON),
        sa.Column("entrypoints", sa.JSON),
        sa.Column("test_files", sa.JSON),
        sa.Column("config_files", sa.JSON),
        sa.Column("source_dirs", sa.JSON),
        sa.Column("total_files", sa.Integer),
        sa.Column("scanned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "repository_pr_patterns",
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sample_size", sa.Integer),
        sa.Column("avg_files_changed", sa.Numeric(8, 2)),
        sa.Column("avg_loc_changed", sa.Numeric(10, 2)),
        sa.Column("pct_with_tests", sa.Numeric(5, 4)),
        sa.Column("pct_with_docs", sa.Numeric(5, 4)),
        sa.Column("common_labels", sa.JSON),
        sa.Column("title_pattern", sa.String(80)),
        sa.Column("median_review_hours", sa.Numeric(10, 2)),
        sa.Column("sample_pr_numbers", sa.JSON),
        sa.Column("test_required", sa.Boolean),
        sa.Column("docs_required", sa.Boolean),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("github_number", sa.Integer, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("body", sa.Text),
        sa.Column("labels", sa.JSON),
        sa.Column("github_state", sa.String(10)),
        sa.Column("github_url", sa.Text),
        sa.Column("score", sa.Integer),
        sa.Column("score_breakdown", sa.JSON),
        sa.Column("eligibility_verdict", sa.String(20)),
        sa.Column("filter_reason", sa.Text),
        sa.Column("reproducibility_confidence", sa.Numeric(3, 2)),
        sa.Column("reproduction_log", sa.Text),
        sa.Column("repro_checks", sa.JSON),
        sa.Column("status", sa.String(20), server_default="detected"),
        sa.Column("abandon_reason", sa.Text),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("repo_id", "github_number", name="uq_issue_repo_number"),
    )
    op.create_index("ix_issues_repo_status", "issues", ["repo_id", "status"])
    op.create_index("ix_issues_score", "issues", ["score"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id")),
        sa.Column("no_brainer_id", sa.Integer),  # FK added below after no_brainer table
        sa.Column("kind", sa.String(20)),
        sa.Column("stage", sa.String(40)),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("cancel_requested", sa.Boolean, server_default=sa.false()),
        sa.Column("abandon_reason", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('pending','running','paused','succeeded','failed','abandoned','cancelled')",
            name="ck_run_status",
        ),
    )
    op.create_index("ix_run_repo_status", "pipeline_runs", ["repo_id", "status"])
    op.create_index("ix_run_status_time", "pipeline_runs", ["status", "created_at"])

    op.create_table(
        "fix_plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id")),
        sa.Column("root_cause", sa.Text),
        sa.Column("target_files", sa.JSON),
        sa.Column("target_functions", sa.JSON),
        sa.Column("approach", sa.Text),
        sa.Column("tests_to_add", sa.JSON),
        sa.Column("risk_notes", sa.Text),
        sa.Column("raw_json", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "patches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=True),
        sa.Column("no_brainer_id", sa.Integer, nullable=True),
        sa.Column("fix_plan_id", sa.Integer, sa.ForeignKey("fix_plans.id")),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id")),
        sa.Column("attempt", sa.Integer, server_default="1"),
        sa.Column("diff_text", sa.Text),
        sa.Column("files_modified", sa.JSON),
        sa.Column("files_added", sa.JSON),
        sa.Column("files_deleted", sa.JSON),
        sa.Column("loc_added", sa.Integer),
        sa.Column("loc_removed", sa.Integer),
        sa.Column("codex_stdout", sa.Text),
        sa.Column("codex_stderr", sa.Text),
        sa.Column("codex_exit_code", sa.Integer),
        sa.Column("duration_seconds", sa.Numeric(8, 2)),
        sa.Column("status", sa.String(20)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("patch_id", sa.Integer, sa.ForeignKey("patches.id", ondelete="CASCADE")),
        sa.Column("command", sa.String(40)),
        sa.Column("command_text", sa.Text),
        sa.Column("exit_code", sa.Integer),
        sa.Column("stdout", sa.Text),
        sa.Column("stderr", sa.Text),
        sa.Column("duration_seconds", sa.Numeric(8, 2)),
        sa.Column("passed", sa.Boolean),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_validation_patch", "validation_results", ["patch_id"])

    op.create_table(
        "issue_comments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("drafted_text", sa.Text),
        sa.Column("posted_text", sa.Text),
        sa.Column("posted_url", sa.Text),
        sa.Column("github_comment_id", sa.Integer),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("status", sa.String(20)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "no_brainer_opportunities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(40)),
        sa.Column("file", sa.String(500)),
        sa.Column("summary", sa.Text),
        sa.Column("proposed_change", sa.Text),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("status", sa.String(20), server_default="detected"),
        sa.Column("pr_id", sa.Integer),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_nobrainer_repo_status", "no_brainer_opportunities", ["repo_id", "status"])

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id")),
        sa.Column("no_brainer_id", sa.Integer, sa.ForeignKey("no_brainer_opportunities.id")),
        sa.Column("patch_id", sa.Integer, sa.ForeignKey("patches.id")),
        sa.Column("type", sa.String(20)),
        sa.Column("upstream_pr_number", sa.Integer),
        sa.Column("upstream_url", sa.Text),
        sa.Column("fork_branch_name", sa.String(200)),
        sa.Column("fork_branch_sha", sa.String(40)),
        sa.Column("upstream_base_branch", sa.String(120)),
        sa.Column("title", sa.Text),
        sa.Column("body", sa.Text),
        sa.Column("files_changed_count", sa.Integer),
        sa.Column("loc_added", sa.Integer),
        sa.Column("loc_removed", sa.Integer),
        sa.Column("status", sa.String(20)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("buffer_until", sa.DateTime(timezone=True)),
        sa.Column("grace_until", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("merged_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pr_repo_status", "pull_requests", ["repo_id", "status"])
    op.create_index("ix_pr_buffer", "pull_requests", ["buffer_until"])
    op.create_index("ix_pr_opened", "pull_requests", ["opened_at"])

    op.create_table(
        "pr_traction",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pr_id", sa.Integer, sa.ForeignKey("pull_requests.id", ondelete="CASCADE")),
        sa.Column("comments_count", sa.Integer, server_default="0"),
        sa.Column("maintainer_engaged", sa.Boolean, server_default=sa.false()),
        sa.Column("reactions_count", sa.Integer, server_default="0"),
        sa.Column("changes_requested", sa.Boolean, server_default=sa.false()),
        sa.Column("approved", sa.Boolean, server_default=sa.false()),
        sa.Column("traction_score", sa.Integer, server_default="0"),
        sa.Column("verdict", sa.String(12)),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_traction_pr_time", "pr_traction", ["pr_id", "scored_at"])

    op.create_table(
        "repo_strategy",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("current_verdict", sa.String(12)),
        sa.Column("reason", sa.Text),
        sa.Column("next_action", sa.String(40)),
        sa.Column("next_action_at", sa.DateTime(timezone=True)),
        sa.Column("history", sa.JSON),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("repo_id", name="uq_strategy_repo"),
    )

    op.create_table(
        "log_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE")),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("level", sa.String(8)),
        sa.Column("stage", sa.String(40)),
        sa.Column("message", sa.Text),
        sa.Column("meta", sa.JSON),
    )
    op.create_index("ix_logs_run_time", "log_events", ["run_id", "ts"])

    op.create_table(
        "contribution_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(8), nullable=False),
        sa.Column("repo_id", sa.Integer, sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("rule_type", sa.String(40)),
        sa.Column("rule_text", sa.Text),
        sa.Column("rule_value", sa.JSON),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contrib_rules_lookup", "contribution_rules", ["scope", "repo_id", "issue_id", "active"])

    op.create_table(
        "settings_kv",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.JSON),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in [
        "settings_kv",
        "contribution_rules",
        "log_events",
        "repo_strategy",
        "pr_traction",
        "pull_requests",
        "no_brainer_opportunities",
        "issue_comments",
        "validation_results",
        "patches",
        "fix_plans",
        "pipeline_runs",
        "issues",
        "repository_pr_patterns",
        "repository_scan",
        "repository_profile",
        "repository_health_signals",
        "repositories",
        "users",
    ]:
        op.drop_table(tbl)
