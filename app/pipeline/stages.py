"""Stage names + per-stage hard timeouts."""

from __future__ import annotations

# Onboarding pipeline ordering
ONBOARDING_STAGES = [
    "fetch_metadata",
    "score_health",
    "fetch_profile",
    "build_code_map",
    "analyze_pr_patterns",
    "scan_no_brainers",
    "detect_issues",
    "done",
]

# Issue-fix pipeline ordering
ISSUE_FIX_STAGES = [
    "reproduce",
    "plan_fix",
    "generate_patch",
    "validate",
    "guardrail",
    "push_branch",
    "post_comment",
    "open_pr",
    "schedule_traction",
    "done",
]

# No-brainer fix pipeline (simpler: skip plan/validate)
NO_BRAINER_STAGES = [
    "prepare",
    "generate_patch",
    "guardrail",
    "push_branch",
    "open_pr",
    "schedule_traction",
    "done",
]

STAGE_TIMEOUTS_SECONDS: dict[str, int] = {
    "fetch_metadata": 30,
    "score_health": 60,
    "fetch_profile": 60,
    "build_code_map": 120,
    "analyze_pr_patterns": 180,
    "scan_no_brainers": 120,
    "detect_issues": 180,
    "reproduce": 600,
    "plan_fix": 300,
    "generate_patch": 600,
    "validate": 900,
    "guardrail": 30,
    "push_branch": 60,
    "post_comment": 30,
    "open_pr": 30,
    "schedule_traction": 5,
    "prepare": 30,
}
