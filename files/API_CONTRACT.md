# API Contract

## Base

- Base path: `/api/v1`
- Auth: `Authorization: Bearer <jwt>` on every endpoint except `/auth/login`
- Content type: `application/json` for body and response
- Errors: `{ "error": "<machine_code>", "message": "<human readable>", "details": {...} }`
- Standard codes: 200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500
- Pagination: `?page=1&page_size=50` (default 20, max 100). Responses include `{ "items": [...], "total": N, "page": 1, "page_size": 20 }`

## Auth

### `POST /auth/login`

```json
// req
{ "email": "you@x.com", "password": "..." }

// res 200
{ "access_token": "...", "token_type": "bearer", "user": { "id": 1, "email": "..." } }
```

### `GET /auth/me`

```json
// res 200
{ "id": 1, "email": "you@x.com", "github_username": "myname", "has_pat": true }
```

---

## Repositories

### `POST /repos`

Add repo with both upstream and fork URLs.

```json
// req
{
  "upstream_url": "https://github.com/facebook/react",
  "fork_url": "https://github.com/myname/react"
}

// res 201
{
  "id": 1,
  "upstream": { "owner": "facebook", "name": "react", "url": "...", "default_branch": "main" },
  "fork":     { "owner": "myname",   "name": "react", "url": "...", "verified": true },
  "language": "javascript",
  "stars": 224000,
  "health_score": null,
  "health_verdict": null,
  "current_phase": "A_initial",
  "paused": false,
  "created_at": "..."
}

// res 400  (fork not of upstream)
{ "error": "fork_not_of_upstream", "message": "..." }

// res 409  (already added)
{ "error": "repo_already_exists", "message": "...", "details": { "id": 7 } }
```

After 201, the onboarding pipeline auto-enqueues. UI should poll `GET /repos/:id` or open `/runs/:run_id/stream`.

### `GET /repos`

```
GET /repos?verdict=alive&phase=C_continue&paused=false&page=1&page_size=50&sort=health_score:desc
```

```json
// res 200
{
  "items": [
    {
      "id": 1, "upstream": {...}, "fork": {...},
      "language": "javascript", "stars": 224000,
      "health_score": 87, "health_verdict": "alive",
      "current_phase": "C_continue",
      "paused": false,
      "open_pr_count": 2, "merged_pr_count": 5,
      "merge_rate": 0.71,
      "last_action_at": "..."
    }
  ],
  "total": 12, "page": 1, "page_size": 50
}
```

### `GET /repos/:id`

```json
// res 200 (full detail)
{
  "id": 1,
  "upstream": {...}, "fork": {...},
  "language": "javascript", "stars": 224000,
  "health_score": 87, "health_verdict": "alive",
  "current_phase": "C_continue",
  "paused": false,
  "profile": { "summary": "...", "run_commands": [...], "tech_stack": [...] },
  "scan": { "total_files": 1234, "entrypoints": [...] },
  "pr_patterns": { "avg_files_changed": 3.2, "test_required": true, ... },
  "strategy": { "current_verdict": "green", "reason": "...", "next_action": "...", ... }
}
```

### `DELETE /repos/:id`

```
204 No Content
```

### `POST /repos/:id/rescan`

```json
// req (optional)
{ "stages": ["health", "profile", "scan", "pr_patterns", "no_brainers"] }

// res 202
{ "run_id": 42, "kind": "rescan", "status": "pending" }
```

### `POST /repos/:id/pause`

```json
// req
{ "reason": "user paused" }

// res 200
{ "id": 1, "paused": true, "pause_reason": "user paused" }
```

### `POST /repos/:id/resume`

```json
// res 200
{ "id": 1, "paused": false }
```

---

## Repo sub-resources

### `GET /repos/:id/health`

```json
// res 200
{
  "current": {
    "alive_score": 87,
    "verdict": "alive",
    "last_commit_at": "...",
    "open_pr_count": 23,
    "merged_pr_count_30d": 18,
    "median_review_hours": 32.5,
    "ci_pass_rate": 0.95,
    "fetched_at": "..."
  },
  "history": [ /* last 10 scans, oldest→newest */ ]
}
```

### `GET /repos/:id/profile`

```json
{
  "summary": "...",
  "run_commands": ["npm install", "npm run dev"],
  "test_commands": ["npm test"],
  "build_commands": ["npm run build"],
  "lint_commands": ["npm run lint"],
  "prerequisites": ["node 18+", "pnpm 8+"],
  "tech_stack": ["javascript", "react"],
  "primary_language": "javascript",
  "raw_readme": "..."
}
```

### `GET /repos/:id/scan`

```json
{
  "total_files": 1234,
  "entrypoints": ["src/index.js"],
  "test_files": ["src/**/*.test.js"],
  "config_files": ["package.json", ".eslintrc.json"],
  "source_dirs": ["src", "lib"],
  "file_tree": { /* nested object */ },
  "scanned_at": "..."
}
```

### `GET /repos/:id/pr-patterns`

```json
{
  "sample_size": 40,
  "avg_files_changed": 3.2,
  "avg_loc_changed": 78.4,
  "pct_with_tests": 0.85,
  "pct_with_docs": 0.40,
  "common_labels": ["bug", "ready-to-merge"],
  "title_pattern": "fix(<scope>): <desc>",
  "median_review_hours": 32.5,
  "test_required": true,
  "docs_required": false,
  "sample_pr_numbers": [12345, 12356, 12378]
}
```

### `GET /repos/:id/strategy`

```json
{
  "current_verdict": "green",
  "reason": "2 of 3 PRs got maintainer engagement",
  "next_action": "escalate_to_issues",
  "next_action_at": "...",
  "history": [
    { "verdict": "yellow", "at": "..." },
    { "verdict": "green", "at": "..." }
  ]
}
```

---

## No-Brainers

### `GET /repos/:id/no-brainers`

```
GET /repos/:id/no-brainers?status=detected&page=1
```

```json
{
  "items": [
    {
      "id": 11,
      "type": "missing_env_docs",
      "file": "README.md",
      "summary": "README references .env but doesn't explain variables",
      "proposed_change": "...",
      "confidence": 0.92,
      "status": "detected",
      "pr_id": null,
      "detected_at": "..."
    }
  ], "total": 6, "page": 1, "page_size": 20
}
```

### `POST /no-brainers/:id/approve`

```json
// res 202
{ "run_id": 99, "kind": "no_brainer_fix", "status": "pending" }
```

### `POST /no-brainers/:id/skip`

```json
// req
{ "reason": "duplicate" }

// res 200
{ "id": 11, "status": "skipped" }
```

---

## Issues

### `GET /repos/:id/issues`

```
GET /repos/:id/issues?status=detected&min_score=60&page=1
```

```json
{
  "items": [
    {
      "id": 222,
      "github_number": 4231,
      "title": "Empty input crashes parser",
      "labels": ["bug"],
      "github_state": "open",
      "github_url": "...",
      "score": 75,
      "eligibility_verdict": "eligible",
      "filter_reason": null,
      "reproducibility_confidence": null,
      "status": "detected"
    }
  ], "total": 18, "page": 1, "page_size": 20
}
```

### `GET /issues/:id`

```json
{
  "id": 222,
  "repo_id": 1,
  "github_number": 4231, "github_url": "...",
  "title": "Empty input crashes parser",
  "body": "...",
  "labels": ["bug"],

  "score": 75,
  "score_breakdown": {
    "reproducible": 30, "maintainer_commented": 15, "small_scope": 15,
    "testability": 10, "recent": 10, "vague_penalty": 0, ...
  },
  "eligibility_verdict": "eligible",
  "filter_reason": null,

  "reproducibility_confidence": 0.91,
  "reproduction_log": "...",

  "status": "pr_opened",
  "abandon_reason": null,

  "fix_plan": { "id": 5, "root_cause": "...", "target_files": [...] },
  "latest_patch": { "id": 12, "diff_text": "...", "loc_added": 34, "loc_removed": 4 },
  "comment": { "id": 33, "posted_url": "...", "status": "posted" },
  "pr": { "id": 88, "upstream_pr_number": 4232, "status": "open" }
}
```

### `POST /issues/:id/skip`

```json
// req
{ "reason": "needs paid service" }

// res 200
{ "id": 222, "status": "skipped" }
```

### `POST /issues/:id/retry`

```json
// res 202
{ "run_id": 101, "kind": "issue_fix", "status": "pending" }
```

---

## Pull Requests

### `GET /prs`

```
GET /prs?repo_id=1&status=open&type=issue_fix&from=2026-04-01&to=2026-05-01&page=1
```

```json
{
  "items": [
    {
      "id": 88,
      "repo_id": 1,
      "type": "issue_fix",
      "issue_id": 222,
      "upstream_pr_number": 4232,
      "upstream_url": "...",
      "title": "...",
      "fork_branch_name": "patchpilot/issue-4231-fix-empty-input",
      "files_changed_count": 2, "loc_added": 34, "loc_removed": 4,
      "status": "open",
      "opened_at": "...",
      "buffer_until": "...",
      "latest_traction": { "traction_score": 4, "verdict": "positive" }
    }
  ], "total": 12, "page": 1, "page_size": 20
}
```

### `GET /prs/:id`

```json
{
  "id": 88,
  "repo": { "id": 1, "upstream": {...}, "fork": {...} },
  "type": "issue_fix",
  "issue": { "id": 222, "title": "...", "github_number": 4231 },
  "upstream_pr_number": 4232,
  "upstream_url": "...",
  "title": "...",
  "body": "...",
  "fork_branch_name": "...",
  "fork_branch_sha": "abc123...",
  "files_changed_count": 2, "loc_added": 34, "loc_removed": 4,
  "status": "open",
  "opened_at": "...", "buffer_until": "...", "grace_until": null,
  "patch": { "id": 12, "diff_text": "..." },
  "traction_history": [
    { "scored_at": "...", "comments_count": 0, "traction_score": 0, "verdict": "pending" },
    { "scored_at": "...", "comments_count": 1, "maintainer_engaged": true, "traction_score": 4, "verdict": "positive" }
  ]
}
```

### `GET /prs/:id/traction`

```json
{ "history": [...same as above...] }
```

---

## Pipeline Runs

### `GET /runs`

```
GET /runs?repo_id=1&status=running&kind=issue_fix&page=1
```

```json
{
  "items": [
    {
      "id": 99,
      "kind": "issue_fix",
      "repo_id": 1, "issue_id": 222,
      "stage": "generate_patch",
      "status": "running",
      "started_at": "...",
      "finished_at": null
    }
  ], "total": 5, "page": 1, "page_size": 20
}
```

### `GET /runs/:id`

```json
{
  "id": 99, "kind": "issue_fix",
  "repo_id": 1, "issue_id": 222,
  "stage": "generate_patch", "status": "running",
  "started_at": "...", "finished_at": null,
  "abandon_reason": null, "error": null,
  "log_count": 142
}
```

### `GET /runs/:id/logs`

History view (paginated).

```
GET /runs/:id/logs?page=1&page_size=200
```

```json
{
  "items": [
    { "id": 1, "ts": "...", "level": "info", "stage": "fetch_metadata", "message": "..." }
  ], "total": 142, "page": 1, "page_size": 200
}
```

### `GET /runs/:id/stream` (SSE)

`Content-Type: text/event-stream`

Events:

```
event: log
data: {"id":1,"ts":"...","level":"info","stage":"...","message":"..."}

event: log
data: {...}

event: end
data: {"status":"succeeded"}
```

### `POST /runs/:id/stop`

```json
// res 200
{ "id": 99, "cancel_requested": true }
```

---

## Metrics

### `GET /metrics/overview`

```json
{
  "total_repos": 12,
  "active_repos": 8,
  "total_prs": 47,
  "open_prs": 9,
  "merged_prs": 28,
  "closed_prs": 10,
  "merge_rate": 0.74,
  "verdict_distribution": { "green": 5, "yellow": 2, "red": 2, "blacklist": 0 }
}
```

### `GET /metrics/timeseries`

```
GET /metrics/timeseries?period=daily&from=2026-04-01&to=2026-05-01&metric=prs_opened
GET /metrics/timeseries?period=weekly&metric=prs_merged
GET /metrics/timeseries?period=monthly&metric=prs_merged
```

```json
{
  "period": "daily",
  "metric": "prs_opened",
  "series": [
    { "ts": "2026-04-01", "value": 2 },
    { "ts": "2026-04-02", "value": 0 },
    ...
  ]
}
```

Metrics supported: `prs_opened`, `prs_merged`, `prs_closed`, `issues_detected`, `issues_fixed`, `runs_succeeded`, `runs_failed`.

### `GET /metrics/by-repo`

```json
{
  "items": [
    { "repo_id": 1, "name": "facebook/react",
      "prs_opened": 5, "prs_merged": 3, "prs_open": 1,
      "merge_rate": 0.60, "last_action_at": "..." }
  ]
}
```

### `GET /metrics/funnel`

```json
{
  "issues_detected": 350,
  "issues_eligible": 120,
  "issues_reproduced": 80,
  "issues_fixed": 45,
  "prs_opened": 45,
  "prs_merged": 22
}
```

---

## Strategy

### `GET /strategy/summary`

```json
{ "green": 5, "yellow": 2, "red": 2, "blacklist": 0,
  "cooldown_queue_size": 1 }
```

---

## Settings

### `GET /settings`

```json
{
  "github_pat_set": true,
  "github_username": "myname",
  "git_commit_email": "you@x.com",
  "git_commit_name": "You",
  "buffer_multiplier": 2.0,
  "max_concurrent_runs": 3,
  "min_health_score": 40,
  "pause_all": false,
  "codex_binary": "codex",
  "codex_healthy": true
}
```

### `PUT /settings`

```json
// req (any subset)
{ "buffer_multiplier": 2.5, "pause_all": true }
// res 200
{ ... updated ... }
```

### `PUT /settings/pat`

```json
// req
{ "github_pat": "ghp_..." }
// res 200
{ "github_pat_set": true, "github_username": "myname" }
```

---

## Activity Log

### `GET /activity`

```
GET /activity?from=2026-04-29&kind=onboarding&status=succeeded&page=1
```

Returns the same shape as `GET /runs` but typically used for the global activity feed.

---

## Error codes (canonical)

| Code | When |
|---|---|
| `unauthorized` | missing/invalid JWT |
| `pat_missing` | endpoint needs PAT, not set |
| `pat_invalid` | GitHub rejected our PAT |
| `repo_not_found` | URL doesn't resolve on GitHub |
| `fork_not_of_upstream` | fork's parent doesn't match upstream |
| `repo_already_exists` | duplicate add |
| `repo_paused` | tried to enqueue work on paused repo |
| `run_not_found` | bad run_id |
| `run_not_cancellable` | run already terminal |
| `rate_limit` | upstream GitHub rate limit hit |
| `validation_failed` | request body bad (Pydantic) |
| `internal_error` | unhandled |
