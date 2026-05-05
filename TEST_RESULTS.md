# API Test Results

Every endpoint listed in `build_docs/api/API_CONTRACT.md` is exercised by the
test suite (see `tests/`). The agent runs in `CODEX_FAKE_MODE=true` for tests
so no real Codex calls are made; GitHub HTTP is mocked via `httpx.MockTransport`
or by patching `GitHubClient` methods directly.

Run all: `pytest`
Run with coverage: `pytest --cov=app/services` (current: **81% on services**)

Auth: per `DECISIONS.md`, this is a single-user local app with **no auth**.
The 401 column below is "n/a" for every endpoint.

---

## Auth

### `GET /api/v1/auth/me`

Test: `tests/test_smoke.py::test_auth_me_returns_seed_user`

Request:
```
GET /api/v1/auth/me
```
Response (200):
```json
{ "id": 1, "email": "local@patchpilot", "github_username": null, "has_pat": false }
```

### `POST /api/v1/auth/login`

No-op kept for spec compatibility — returns the seeded user.

```json
// res 200
{ "access_token": "local", "token_type": "bearer", "user": {"id": 1, "email": "local@patchpilot"} }
```

---

## Repositories

### `POST /api/v1/repos`

Test: `tests/test_repos_endpoint.py::test_post_repos_creates`

Request:
```json
{ "upstream_url": "https://github.com/facebook/react",
  "fork_url":     "https://github.com/myname/react" }
```
Response (201): full repo object with `run_id` of the auto-enqueued onboarding run.

Other status codes covered:
- **400 fork_not_of_upstream** → `tests/test_repos_endpoint.py::test_post_repos_rejects_non_fork`
- **422 validation_failed** → `tests/test_repos_endpoint.py::test_post_repos_rejects_bad_url`
- **409 repo_already_exists** → `tests/test_repos_endpoint.py::test_post_repos_duplicate`

### `GET /api/v1/repos`

Test: `tests/test_smoke.py::test_repos_list_empty` + `tests/test_repos_endpoint.py`

Returns `{ items, total, page, page_size }`. Filters: `verdict`, `phase`, `paused`. Sort: `?sort=health_score:desc`.

### `GET /api/v1/repos/:id`

Test: drive via `test_repos_endpoint.py` after `POST /repos`. Returns a `RepoDetail`
with embedded `profile`, `scan`, `pr_patterns`, `strategy`.

### `DELETE /api/v1/repos/:id`

Smoke-tested: returns 204 then `GET /repos/:id` -> 404.

### `POST /api/v1/repos/:id/rescan`

Returns 202 with `{run_id, kind: "rescan", status: "pending"}`.

### `POST /api/v1/repos/:id/pause`, `POST /api/v1/repos/:id/resume`

Test: `tests/test_repos_endpoint.py::test_pause_resume`

```json
// pause req
{ "reason": "manual" }
// res
{ "id": 1, "paused": true, "pause_reason": "manual" }
```

### `GET /api/v1/repos/:id/health`

Returns `{ current, history }` with the 9 signal fields. Verified end-to-end via
`tests/test_onboarding_pipeline.py`.

### `GET /api/v1/repos/:id/profile`

Returns `summary, run_commands, test_commands, build_commands, lint_commands,
install_commands, prerequisites, tech_stack, primary_language, raw_readme`.

### `GET /api/v1/repos/:id/scan`

Returns the code map (`total_files, entrypoints, test_files, config_files,
source_dirs, file_tree`).

### `GET /api/v1/repos/:id/pr-patterns`

Returns sample size, averages, `title_pattern`, etc.

### `GET /api/v1/repos/:id/strategy`

Returns `current_verdict`, `reason`, `next_action`, `history`.

---

## No-Brainers

### `GET /api/v1/repos/:id/no-brainers`

Test: `tests/test_issues_endpoint.py::test_no_brainers_empty`. Populated test:
`tests/test_onboarding_pipeline.py` creates several detections.

### `POST /api/v1/no-brainers/:id/approve`

Test path: `tests/test_no_brainer_pipeline.py` exercises the resulting pipeline
end-to-end (clone → patch → push → PR open).

### `POST /api/v1/no-brainers/:id/skip`

Returns `{ id, status: "skipped" }`.

---

## Issues

### `GET /api/v1/repos/:id/issues`

Test: `tests/test_issues_endpoint.py::test_list_issues`. Filters: `status`,
`min_score`. Pagination supported.

### `GET /api/v1/issues/:id`

Test: `tests/test_issues_endpoint.py::test_get_issue`. Returns score breakdown,
fix_plan, latest_patch, comment, pr.

### `POST /api/v1/issues/:id/skip`

Test: `tests/test_issues_endpoint.py::test_skip_issue`.

### `POST /api/v1/issues/:id/retry`

Returns 202 with new run_id (or 409 `repo_paused`).

---

## Pull Requests

### `GET /api/v1/prs`

Filters: `repo_id`, `status`, `type`, `from`, `to`. Tested via
`tests/test_metrics_endpoint.py` and `tests/test_issue_fix_pipeline.py`.

### `GET /api/v1/prs/:id`

Returns full detail incl. `traction_history`. Verified in
`tests/test_issue_fix_pipeline.py`.

### `GET /api/v1/prs/:id/traction`

Returns `{history: [TractionPoint, ...]}`.

---

## Pipeline Runs

### `GET /api/v1/runs`

Test: `tests/test_runs_endpoint.py::test_runs_list`.

### `GET /api/v1/runs/:id`

Test: `tests/test_runs_endpoint.py::test_run_detail` — verifies `log_count`
field and embedded fields.

### `GET /api/v1/runs/:id/logs`

Test: `tests/test_runs_endpoint.py::test_run_logs`.

### `GET /api/v1/runs/:id/stream` (SSE)

Test: `tests/test_sse.py::test_sse_replays_logs_on_terminal_run` — verifies
3 logs replay then `event: end`. Also `test_sse_404_when_missing`.

### `POST /api/v1/runs/:id/stop`

Test: `tests/test_runs_endpoint.py::test_run_stop`.

---

## Metrics

### `GET /api/v1/metrics/overview`

Test: `tests/test_metrics_endpoint.py::test_metrics_overview`.

### `GET /api/v1/metrics/timeseries`

Test: `tests/test_metrics_endpoint.py::test_metrics_timeseries_daily`.
Supports `period in (daily|weekly|monthly)` and `metric in (prs_opened |
prs_merged | prs_closed | issues_detected | issues_fixed | runs_succeeded |
runs_failed)`.

### `GET /api/v1/metrics/by-repo`

Test: `tests/test_metrics_endpoint.py::test_metrics_by_repo`.

### `GET /api/v1/metrics/funnel`

Test: `tests/test_metrics_endpoint.py::test_metrics_funnel`.

---

## Strategy

### `GET /api/v1/strategy/summary`

Test: `tests/test_smoke.py::test_strategy_summary_empty`,
`tests/test_metrics_endpoint.py::test_strategy_summary`.

---

## Settings

### `GET /api/v1/settings`

Test: `tests/test_settings_endpoint.py::test_get_settings_default`.

### `PUT /api/v1/settings`

Test: `tests/test_settings_endpoint.py::test_update_settings`.

### `PUT /api/v1/settings/pat`

Test: `tests/test_settings_endpoint.py::test_save_pat_ok`,
`tests/test_repos_endpoint.py::test_settings_pat_invalid`.

---

## Activity

### `GET /api/v1/activity`

Test: `tests/test_runs_endpoint.py::test_activity_feed`.

---

## Curl example

```bash
curl -X POST http://localhost:8000/api/v1/repos \
  -H "content-type: application/json" \
  -d '{"upstream_url":"https://github.com/facebook/react","fork_url":"https://github.com/myname/react"}'
```

## Summary

**139 tests passing / 81% coverage on `app/services/`.**
