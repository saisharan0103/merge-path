# Pipeline State Machine

## PipelineRun

A `PipelineRun` represents one execution of either the **Onboarding** pipeline or the **Issue Fix** pipeline.

### Status enum

```python
class RunStatus(str, Enum):
    pending     = "pending"      # queued, not yet started
    running     = "running"      # actively executing a stage
    paused      = "paused"       # user clicked pause
    succeeded   = "succeeded"    # all stages completed
    failed      = "failed"       # unrecoverable error
    abandoned   = "abandoned"    # logically gave up (e.g., low repro confidence)
    cancelled   = "cancelled"    # user clicked stop mid-run
```

### Stage enum (current stage within a run)

**Onboarding pipeline:**
```
fetch_metadata → score_health → fetch_profile → build_code_map
→ analyze_pr_patterns → scan_no_brainers → detect_issues → done
```

**Issue Fix pipeline:**
```
reproduce → plan_fix → generate_patch → validate → guardrail
→ push_branch → post_comment → open_pr → schedule_traction → done
```

## Transitions

```
   ┌────────┐
   │pending │
   └───┬────┘
       │ worker picks up
       ↓
   ┌─────────┐  user clicks pause   ┌────────┐
   │ running ├─────────────────────→│ paused │
   └───┬─────┘  user clicks resume  └────┬───┘
       │ ←────────────────────────────────┘
       │
       ├─ all stages OK ────────→ succeeded
       │
       ├─ unrecoverable err ────→ failed
       │
       ├─ logical skip (low conf)→ abandoned
       │
       └─ user clicks stop ─────→ cancelled
```

## Stop Controller (mid-run interrupt)

User clicks "Stop" on a running pipeline:

1. Frontend → `POST /runs/:id/stop`
2. Backend writes `runs.cancel_requested = true` in DB
3. Celery worker checks `cancel_requested` flag **between every stage and at every safe point inside long stages**
4. On detection: cleanup (kill subprocess, close git ops), set `status = cancelled`, emit final log

**Safe-point checks inside long stages:**
- `clone_repo` → after clone completes, before next op
- `install_deps` → after install completes
- `run_tests` → check before each test command
- `codex_call` → cannot interrupt mid-Codex; check immediately after returns

The worker sets a SIGTERM handler that kills child subprocesses cleanly.

## Retry Policy

| Failure | Action | Max retries | Backoff |
|---|---|---|---|
| GitHub API 5xx | Retry | 3 | exponential 2s, 8s, 30s |
| GitHub rate limit (403 + remaining=0) | Wait until reset | 1 | until reset header |
| Network / DNS | Retry | 3 | exponential |
| Clone fail (fatal: repo not found) | No retry | 0 | — |
| Install deps fail | Retry once | 1 | 5s |
| Test run fail (non-zero exit) | Treat as failure signal, NOT retry | 0 | — |
| Codex CLI returns malformed output | Retry with stricter prompt | 1 | 0s |
| Codex CLI timeout | Retry once with smaller scope hint | 1 | 0s |
| Patch validation fail | Regenerate patch | 2 | 0s |
| Guardrail rejection | Ask Codex to shrink | 1 | 0s |
| Push branch fail (auth) | Fail fast | 0 | — |
| Push branch fail (non-fast-forward) | Force-with-lease, retry | 1 | 0s |
| Open PR fail (already exists) | Update existing, don't error | 0 | — |

After max retries → run goes to `failed` or `abandoned` (depending on whether it's an error or a logical skip).

## Sample DB row lifecycle

```sql
-- T0: user adds repo
INSERT pipeline_runs (id=1, repo_id=42, kind='onboarding', status='pending', stage=null);

-- T1: worker picks up, starts fetch_metadata
UPDATE pipeline_runs SET status='running', stage='fetch_metadata', started_at=now() WHERE id=1;

-- T2: stage done, moves to score_health
UPDATE pipeline_runs SET stage='score_health' WHERE id=1;

-- T3: all stages succeeded
UPDATE pipeline_runs SET status='succeeded', stage='done', finished_at=now() WHERE id=1;
```

For issue-fix pipeline, on abandonment (low repro confidence):
```sql
UPDATE pipeline_runs SET status='abandoned', stage='reproduce',
    abandon_reason='reproduction_confidence_below_threshold' WHERE id=99;
```

## Stage Timeouts

Each stage has a hard timeout. If exceeded, the stage fails:

| Stage | Timeout |
|---|---|
| fetch_metadata | 30s |
| score_health | 60s |
| fetch_profile | 60s |
| build_code_map | 120s |
| analyze_pr_patterns | 180s |
| scan_no_brainers | 120s |
| detect_issues | 180s |
| reproduce | 600s (10m) |
| plan_fix (Codex) | 300s |
| generate_patch (Codex) | 600s |
| validate (run tests) | 900s (15m) |
| guardrail | 30s |
| push_branch | 60s |
| post_comment | 30s |
| open_pr | 30s |

Configurable via env or settings.

## Idempotency

Every stage must be idempotent — re-running it on the same input must produce the same effect. This is critical for retries:

- `fetch_metadata` — reads from GitHub, writes to DB with upsert
- `score_health` — recomputes from signals, overwrites
- `push_branch` — `git push --force-with-lease` (safe even if branch exists)
- `open_pr` — first checks if PR for this issue/branch already exists; if so, updates instead of creating
- `post_comment` — checks `issue_comments` table for existing comment by us; if exists, no-op (does NOT post again)

## Pause Semantics

Pause is per-repo, not per-run. When a repo is paused:
- No new runs are enqueued for that repo
- In-flight runs continue to completion (not cancelled)
- Scheduled traction checks for that repo are skipped until unpaused
