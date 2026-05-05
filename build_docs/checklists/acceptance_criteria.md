# Acceptance Criteria

Concrete pass/fail criteria per feature. Each item must be demonstrable. Used as the QA gate during handoff.

## A. Auth & Settings

- [ ] User can log in via `POST /auth/login` and receive a valid JWT
- [ ] All other endpoints reject requests without `Authorization: Bearer <jwt>` (401)
- [ ] User can set GitHub PAT via `PUT /settings/pat`; PAT is encrypted at rest in `users.github_pat_encrypted`
- [ ] After PAT is set, `GET /auth/me` returns `has_pat: true` and the resolved `github_username`
- [ ] If PAT is invalid, save returns `400 pat_invalid`
- [ ] `GET /settings` returns codex healthy status reflecting actual binary presence

## B. Add Repo

- [ ] `POST /repos` with valid upstream + valid fork → 201, repo row created, onboarding pipeline auto-enqueued
- [ ] `POST /repos` with fork that is NOT a fork of upstream → `400 fork_not_of_upstream`
- [ ] `POST /repos` with already-added repo → `409 repo_already_exists`
- [ ] `POST /repos` with non-GitHub URL → `422 validation_failed`
- [ ] `POST /repos` when fork is private and PAT lacks read access → `400 pat_invalid` (or `400 fork_not_accessible`)
- [ ] After 201, within 60s `GET /repos/:id` returns a non-null `health_score` and `health_verdict`

## C. Repo Health Scoring

- [ ] `GET /repos/:id/health` returns `current` with all 9 signal fields populated
- [ ] `health_verdict` is one of `alive | weak | stale`, computed per spec
- [ ] Re-scanning via `POST /repos/:id/rescan` produces a new row in `repository_health_signals` and updates `repositories.health_score`
- [ ] History endpoint returns last 10 scans, oldest→newest

## D. Repo Profile + Code Map

- [ ] `GET /repos/:id/profile` returns parsed `summary`, `run_commands`, `test_commands`, `build_commands`, `prerequisites`, `tech_stack`, `primary_language`
- [ ] Profile correctly identifies primary language for at least: Python, JS/TS, Go, Rust, Java repos (test against 1 sample each)
- [ ] `GET /repos/:id/scan` returns `total_files`, `entrypoints`, `test_files`, `config_files`, `source_dirs`, `file_tree`
- [ ] Scan correctly identifies test files for each of the 5 stacks

## E. PR Pattern Analyzer

- [ ] `GET /repos/:id/pr-patterns` populated after onboarding for repos with ≥ 20 merged PRs
- [ ] `pct_with_tests`, `pct_with_docs`, `avg_files_changed`, `avg_loc_changed`, `median_review_hours` are numeric and reasonable
- [ ] `title_pattern` correctly extracts conventional commit pattern when present
- [ ] `test_required` boolean derived from `pct_with_tests > 0.6`

## F. No-Brainer Scanner

- [ ] After onboarding, `GET /repos/:id/no-brainers` returns at least one item for repos with obvious gaps
- [ ] Each item has `type`, `file`, `summary`, `proposed_change`, `confidence`
- [ ] Detected types include: `missing_env_docs`, `broken_link`, `missing_test_command`, `missing_prerequisites`, `no_windows_notes`, `no_troubleshooting`, `broken_readme_command`
- [ ] `POST /no-brainers/:id/approve` enqueues a `no_brainer_fix` pipeline run
- [ ] On approval, agent creates branch, commits, pushes to fork, opens PR; resulting `pull_requests` row links to no-brainer

## G. Issue Detection + Scoring

- [ ] `GET /repos/:id/issues` lists open upstream issues
- [ ] Each issue has a `score` (0–100) and `eligibility_verdict`
- [ ] Issues filtered out by hard filters have `filter_reason` populated
- [ ] Score breakdown visible in `GET /issues/:id`
- [ ] No-repro issues, UI bugs, vague requests are correctly filtered

## H. Reproduction Engine

- [ ] On a known-reproducible issue, `reproducibility_confidence` ≥ 0.7
- [ ] On a vague issue, confidence < 0.7 → run goes to `abandoned`, no comment posted, no PR opened
- [ ] Reproduction logs persisted to `issues.reproduction_log`
- [ ] Stack trace parsing extracts `target_file:line` for the fix planner
- [ ] Reproduction respects per-stage timeout

## I. Codex Integration

- [ ] `CodexRunner.health_check()` returns true when binary present, false otherwise
- [ ] Plan stage produces `fix_plan.json` and parses into `fix_plans` row
- [ ] Patch stage produces a non-empty diff and persists to `patches`
- [ ] Diff size is captured (`loc_added`, `loc_removed`)
- [ ] Scope violation (Codex modifying non-allowlisted files) is detected and triggers retry
- [ ] Empty diff triggers retry
- [ ] Codex timeout produces `error=codex_timeout` in patch row
- [ ] All Codex stdout/stderr captured in `patches.codex_stdout/stderr`

## J. Validation

- [ ] For each of the 5 stacks, validation correctly invokes the test command
- [ ] Test failure feeds back into patch retry loop with truncated stderr
- [ ] After 2 patch retries with continued validation failure → issue abandoned
- [ ] `validation_results` rows created per command
- [ ] Lint failures only on unrelated files do NOT block PR

## K. Guardrails

- [ ] Patch with > N files (where N = repo's avg × 1.5, capped at 5) → reject and retry
- [ ] Patch with > LOC budget → reject and retry
- [ ] Patch touching `package-lock.json` or similar → reject
- [ ] Patch with empty diff → reject

## L. Issue Comment

- [ ] Comment generation only invoked when reproducibility ≥ 0.7
- [ ] Generated comment posted to upstream issue via API
- [ ] `issue_comments` row has `posted_url` and `github_comment_id`
- [ ] Comment passes validation (no "Can I work on this?", word count ≤ 100)
- [ ] If issue already has a comment from us → not posted twice (idempotent)

## M. PR Creation

- [ ] PR opened from `{fork_owner}:{branch}` → `{upstream_default_branch}`
- [ ] `maintainer_can_modify=true` set on PR
- [ ] PR body contains `## What changed`, `## Why`, `## How tested`, `Fixes #N`
- [ ] PR title matches repo title pattern
- [ ] `pull_requests` row created with `upstream_pr_number`, `upstream_url`, `opened_at`, `buffer_until`, `grace_until`
- [ ] If PR for same branch already open → updated instead of duplicated

## N. Fork Operations

- [ ] Initial clone is from fork (not upstream)
- [ ] `upstream` remote is added and `git fetch upstream` runs successfully
- [ ] Default branch on fork is synced with upstream before each issue
- [ ] Branches use the `patchpilot/issue-N-slug` or `patchpilot/no-brainer-...` pattern
- [ ] Push uses `--force-with-lease` when overwriting

## O. Buffer + Traction

- [ ] After PR open, `buffer_until = now + median_review_hours * 2`, min 7d, max 21d
- [ ] After buffer with zero response, `grace_until` extends 5 more days
- [ ] Traction polling runs every 30 minutes (Celery beat) and updates `pr_traction`
- [ ] Traction score correctly applies points per spec
- [ ] PR closed without merge → `−5`; merged → `+10`; etc.

## P. Strategy Adapter

- [ ] After buffer + grace, `repo_strategy.current_verdict` updates per traction sum
- [ ] Verdict transitions: green/yellow/red/blacklist applied correctly
- [ ] Red verdict sets `cooldown_until = now + 30d`; recheck happens after
- [ ] Blacklist is permanent (no recheck scheduled)
- [ ] Strategy history appended to `repo_strategy.history`

## Q. Pause / Resume / Stop

- [ ] `POST /repos/:id/pause` sets `paused=true` and blocks new runs from being enqueued
- [ ] In-flight runs continue (not cancelled)
- [ ] `POST /repos/:id/resume` clears flag and resumes scheduling
- [ ] `POST /runs/:id/stop` sets `cancel_requested=true`, run reaches `cancelled` within 60s
- [ ] Stopped run does not leave dangling git ops or temp files

## R. Frontend Pages

- [ ] `/` Dashboard renders all stat cards, time-series chart, recent activity feed, verdict pie, funnel
- [ ] `/repos` table loads with sorting, filtering, pagination
- [ ] `/repos/:id` shows all 9 tabs and switches correctly
- [ ] `/scores` leaderboard sorts by health score
- [ ] `/issues` lists with filters
- [ ] `/issues/:id` shows score breakdown, repro log, comment, PR link
- [ ] `/prs` "By Repo" and "All" toggles work
- [ ] `/prs/:id` shows traction timeline
- [ ] `/strategy` shows verdict table + cooldown queue + blacklist
- [ ] `/activity` streams new runs as they happen (or polls every 5–10s)
- [ ] `/settings` lets user save PAT, fork credentials, buffer multiplier, pause-all
- [ ] Classic theme tokens applied across all pages (cream bg, serif headings, dense tables)

## S. Logs / SSE

- [ ] `GET /runs/:id/stream` opens SSE connection successfully
- [ ] Live log events appear in run detail page within 1s of emission
- [ ] On run end, `event: end` is sent and connection closes
- [ ] On reconnect, last 200 logs are replayed (no missed events)
- [ ] `GET /runs/:id/logs` returns paginated history
- [ ] Logs older than 90 days are GC'd

## T. Metrics

- [ ] `GET /metrics/overview` matches DB counts exactly
- [ ] `GET /metrics/timeseries?period=daily|weekly|monthly` returns correct buckets
- [ ] `GET /metrics/by-repo` returns all repos with PR counts
- [ ] `GET /metrics/funnel` returns issues→eligible→reproduced→fixed→PR→merged numbers

## U. Multi-language E2E

Run full pipeline against 5 real repos, one per stack:

- [ ] Python repo: onboarding → no-brainer PR opens
- [ ] JS/TS repo: onboarding → no-brainer PR opens
- [ ] Go repo: onboarding → no-brainer PR opens
- [ ] Rust repo: onboarding → no-brainer PR opens
- [ ] Java repo (Maven): onboarding → no-brainer PR opens

For each, document in `E2E_RESULTS.md` the repo URL, run ID, and PR URL.

## V. Done flag

The build is **not done** until **every box above is checked** and the artifacts in `checklists/done_checklist.md` are produced.
