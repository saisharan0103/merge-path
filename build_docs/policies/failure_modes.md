# Failure Modes Catalog

What goes wrong, what the agent does about it.

## GitHub API failures

| Failure | Detection | Action | Status |
|---|---|---|---|
| 401 (PAT invalid/revoked) | response code | Mark all repos `paused`, surface in `/settings`, alert UI | Halt all runs |
| 403 (rate limit, primary) | `X-RateLimit-Remaining: 0` | Wait until `X-RateLimit-Reset`, then resume | Run paused |
| 403 (abuse / secondary rate limit) | `Retry-After` header | Wait that duration + 30s jitter | Run paused |
| 404 (repo gone) | response code | Mark repo `red`, log, surface | Repo halted |
| 422 (validation, e.g. bad PR head) | response code | Log, fail run, do NOT retry | Run failed |
| 5xx | response code | Exponential backoff: 2s, 8s, 30s; 3 retries | Retry |
| Network/DNS | exception | Same backoff | Retry |
| GraphQL throttle | error in body | Switch to REST for that call, retry once | Retry |

## Clone failures

| Failure | Action |
|---|---|
| Repo not accessible (private, deleted) | Mark repo `red`, fail run |
| Disk full | Halt all runs, alert UI, do not auto-recover |
| Submodule fetch fails | Continue without submodules, log warning |
| Clone takes > 5 min | Mark fail (run timeout), retry once with `--depth 1` |
| `.git` corruption from previous run | `rm -rf` working dir, re-clone |

## Sandbox / install failures

| Failure | Action |
|---|---|
| Install command not found (`pnpm` etc) | Try next attempt in fallback list |
| Install times out | Retry once with `--prefer-offline` style flag if supported |
| Install fails (non-zero exit) | Capture stderr; if missing system dep (e.g. libxml2), abandon issue, log "missing system dep: X" — recommend in UI |
| Install requires interactive prompt | Set `CI=true`, retry once |
| `node_modules`/`venv` permissions | Recreate working dir from scratch, retry once |

## Codex failures

See `specs/03_codex_integration.md` "Failure handling" section. Summary:

| Codex result | Action |
|---|---|
| Empty diff | Retry once with stricter prompt |
| Scope violation (touched non-allowed file) | Retry once with explicit allowlist |
| Diff exceeds LOC budget | Retry with stricter LOC cap |
| Timeout | Retry once with reduced scope |
| Aborted via `abort.txt` | Mark issue abandoned, persist abort reason |
| Malformed plan JSON | Retry once with strict schema reminder |
| Non-zero exit | Capture stderr, retry once |

After retries → abandon issue with `abandon_reason='codex_failed:<error>'`.

## Validation failures

| Failure | Action |
|---|---|
| Existing tests fail (pre-patch baseline) | Patch is NOT to blame. Mark validation skipped, log warning. Decision: still proceed only if regression test alone passes; else abandon issue with reason `repo_tests_already_broken` |
| New patch tests fail | Send failure context back to patch generator, retry up to 2 times |
| Lint fails (touching only patched files) | Retry patch once with lint output included |
| Lint fails (touching unrelated files only) | Skip lint gate, log warning, continue |
| Build fails | Same as test fail |
| Test runner not installed | Try alternates; if none work, mark validation skipped, but do NOT open PR — abandon |
| Test takes > timeout | Retry with `-x` (fail fast); if still timeout, abandon |

## Git push failures

| Failure | Action |
|---|---|
| Auth error (PAT lost write access to fork) | Mark repo paused, surface in UI |
| Non-fast-forward | `git push --force-with-lease`, retry once |
| Branch already exists with different content | `--force-with-lease` overwrites |
| Network timeout during push | Retry 2x with backoff |
| Unrelated histories | Abandon issue, log; suggests fork is in bad shape |

## PR open failures

| Failure | Action |
|---|---|
| PR already exists for this branch | Update existing instead of creating; persist same `pull_requests` row |
| PR refused (e.g., upstream archived) | Mark repo `red` |
| Maintainer-blocked author (banned) | Mark repo `blacklist` for this user |
| Comment posting failed | Continue to PR creation; comment is best-effort |
| Rate limit hit between comment and PR | Wait, retry PR open |

## Reproduction failures

| Failure | Action |
|---|---|
| Cannot run setup commands | Try doc-fix path: open no-brainer PR fixing the setup docs we hit. Skip the original issue. |
| No reproduction steps in issue | Skip issue (filter at scoring stage; should not reach here) |
| Reproduction matches issue | Confidence ≥ 0.7, proceed |
| Reproduction does not match | Confidence < 0.7, skip silently — no comment, no PR |
| Reproduction is flaky (passes 50% of attempts) | Run 5 times; if < 80% reproduction rate, treat as confidence < 0.7 |
| Reproduction needs network to specific external service | Skip (filter caught this) |

## Traction polling failures

| Failure | Action |
|---|---|
| PR no longer findable | Mark `closed` with `unknown` reason, log |
| Comment lookup fails | Retry next polling cycle |
| Repo became private | Mark repo `red`, halt traction polling |
| User's PAT lost permission | Pause repo, alert |

## Worker crashes

| Failure | Action |
|---|---|
| Celery worker OOM | Beat job detects orphan `running` runs older than max stage timeout, marks `failed` |
| Worker restart mid-stage | Same orphan-detection logic; affected run is failed (no auto-retry — let user decide) |
| Database connection lost | Worker exits, supervisor restarts |
| Redis connection lost | Worker exits, supervisor restarts; SSE clients reconnect |

## Disk and resource

| Failure | Action |
|---|---|
| Working dir > 10GB | GC oldest first, halt new clones until below 5GB |
| Process count exceeded | Drop new Celery tasks (queue depth limit), surface backpressure |
| Postgres disk full | Halt all writes, alert |

## User-side errors

| Failure | Action |
|---|---|
| User submits non-GitHub URL | Reject in API with `validation_failed` |
| Fork URL doesn't match upstream | Reject with `fork_not_of_upstream` |
| User pauses repo mid-run | In-flight runs continue; new runs blocked |
| User stops a run | Cancel signal flag; worker handles at next safe point |
| User deletes repo while runs active | Cascade delete; running runs get cancelled at safe point |

## Concurrency / race conditions

| Failure | Action |
|---|---|
| Two onboarding runs enqueued for same repo | Postgres advisory lock by `repo_id`; second waits, no-ops if first succeeded recently |
| Two issue-fix runs for same issue | Lock by `issue_id`; second is rejected with `409 already_running` |
| Strategy adapter recomputes during PR state change | Use `SELECT ... FOR UPDATE` on `repo_strategy` row |

## Surfacing failures in UI

Failed runs appear in `/activity` and on the relevant `/repos/:id` Logs tab.
Each failed run shows:
- Stage failed at
- Error code (machine-readable)
- Last 50 lines of log
- "Retry" button (where applicable)

Permanent failures (e.g. `repo_red_404`) disable the retry button and show the verdict reason.
