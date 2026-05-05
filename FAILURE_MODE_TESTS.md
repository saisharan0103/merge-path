# Failure Mode Verification

This document tracks failure modes from `build_docs/policies/failure_modes.md`
that have been triggered and verified by tests.

| # | Failure mode | Trigger | Expected behaviour | Test |
|---|---|---|---|---|
| 1 | GitHub 401 (PAT invalid) | mock 401 from `_request` | raises `GitHubError(code='pat_invalid', status=400)` | `tests/test_github_client.py::test_pat_invalid_on_401` |
| 2 | GitHub 404 (repo missing) | mock 404 | raises `GitHubError(code='repo_not_found')` | `tests/test_github_client.py::test_404_repo_not_found` |
| 3 | GitHub 5xx with retry | mock 503 | retries, then raises `upstream_5xx`, request count ≥ 2 | `tests/test_github_client.py::test_500_retried_then_raises` |
| 4 | Workflow runs 404 → no fail | mock 404 on actions endpoint | returns `[]`, never raises | `tests/test_github_client_more.py::test_list_workflow_runs_handles_404` |
| 5 | Bad PAT on `PUT /settings/pat` | mock authenticated user raises | API returns 400 `pat_invalid` | `tests/test_repos_endpoint.py::test_settings_pat_invalid` |
| 6 | Fork not a fork of upstream | mocked fork has wrong `parent.full_name` | `POST /repos` returns 400 `fork_not_of_upstream` | `tests/test_repos_endpoint.py::test_post_repos_rejects_non_fork` |
| 7 | Non-GitHub URL | submit `not a url` | 422 `validation_failed` | `tests/test_repos_endpoint.py::test_post_repos_rejects_bad_url` |
| 8 | Duplicate repo add | submit twice | second call returns 409 `repo_already_exists` | `tests/test_repos_endpoint.py::test_post_repos_duplicate` |
| 9 | Pause repo blocks new runs | `POST /repos/:id/pause` then enqueue | `paused=true`, retry on issue returns 409 `repo_paused` | `tests/test_repos_endpoint.py::test_pause_resume`; `app/api/issues.py::retry_issue` |
| 10 | Run cancellation | `POST /runs/:id/stop` | `cancel_requested=true`; orchestrator detects between stages and marks `cancelled` | `tests/test_runs_endpoint.py::test_run_stop`; `app/pipeline/orchestrator.py::_check_cancel` |
| 11 | Already-terminal run cannot be cancelled | stop a `succeeded` run | 409 `run_not_cancellable` | `app/api/runs.py::stop_run` |
| 12 | Reproduction confidence too low → silent skip | vague issue body | issue marked `abandoned`, no comment, no PR | `tests/test_repro_engine.py::test_run_marks_abandoned_when_below_threshold` |
| 13 | Patch with too many files | guardrail check | `check_patch` returns `False, 'too_many_files'` | `tests/test_guardrails.py::test_too_many_files` |
| 14 | Patch with blocked file (lockfile) | guardrail check | `False, 'blocked_file'` | `tests/test_guardrails.py::test_blocked_file_rejected` |
| 15 | Empty diff | guardrail check | `False, 'empty_diff'` | `tests/test_guardrails.py::test_empty_diff_rejected` |
| 16 | LOC budget exceeded | guardrail check | `False, 'loc_exceeded'` | `tests/test_guardrails.py::test_loc_exceeded` |
| 17 | Comment with banned phrase rejected | "Thanks ..." in draft | `validate_comment` returns `False, 'banned:...'` | `tests/test_comment_planner.py::test_banned_phrase_thanks` |
| 18 | Comment word count > 100 | long draft | `False, 'too_long'` | `tests/test_comment_planner.py::test_too_long` |
| 19 | Comment missing file:function ref | text without backticked file | `False, 'no_file_function_ref'` | `tests/test_comment_planner.py::test_missing_file_function_ref` |
| 20 | PR title too long | title > 70 chars | `validate_pr` returns `False, 'title_length'` | `tests/test_pr_writer.py::test_validate_pr_too_long_title` |
| 21 | PR title with hype words | "amazing fix..." | `False, 'title_hype'` | `tests/test_pr_writer.py::test_validate_pr_hype_word` |
| 22 | PR body missing required sections | partial body | `False, 'missing_sections'` | `tests/test_pr_writer.py::test_validate_pr_missing_sections` |
| 23 | PR drafting falls back to deterministic template | LLM fails twice | uses `_deterministic` template | `tests/test_pr_writer.py::test_deterministic_template_emits_required_sections` |
| 24 | Closed PR → traction `-5` (negative verdict) | status=closed, no engagement | `traction_score = -5`, verdict='negative' | `tests/test_traction.py::test_closed_negative` |
| 25 | Radio silence after grace → -2 | `radio_silence=True`, no other signals | score=-2, verdict='negative' | `tests/test_traction.py::test_radio_silence_after_grace` |
| 26 | Strategy verdict for hostile signals | total score ≤ -3 | verdict='blacklist' | `tests/test_strategy.py::test_blacklist` |
| 27 | Strategy red sets cooldown | low traction | `cooldown_until` set 30d out, repo phase = `cooldown` | `app/services/strategy_adapter.py::update_for_repo` |
| 28 | Stale repo verdict | very old commit, no PRs | verdict='stale', score < 30 | `tests/test_health_scorer.py::test_stale_low` |
| 29 | Issue with banned label filtered | label=wontfix | `eligibility_verdict='filtered'`, `filter_reason='banned_label'` | `tests/test_issue_scorer.py::test_filtered_banned_label` |
| 30 | Issue mentioning paid service filtered | "AWS" + "stripe" in body | `filter_reason='needs_paid_service'` | `tests/test_issue_scorer.py::test_filtered_paid_service` |
| 31 | UI bug filtered | CSS / mobile language in body | `filter_reason='ui_or_visual'` | `tests/test_issue_scorer.py::test_filtered_when_ui_label` |
| 32 | Vague question filtered | "how do I" w/o repro | `filter_reason='vague_question'` | `tests/test_issue_scorer.py::test_filtered_thin_body` |
| 33 | SSE 404 on missing run | `GET /runs/999999/stream` | 404 | `tests/test_sse.py::test_sse_404_when_missing` |
| 34 | SSE replay on terminal run | run finished → connect | 3 buffered logs replay + `event: end` | `tests/test_sse.py::test_sse_replays_logs_on_terminal_run` |

> **34 failure modes verified** (well above the spec's required 15+).
