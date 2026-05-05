# Architecture Spec

> **Status:** Reflects locked decisions in `DECISIONS.md`. Single-user, local
> SQLite, ARQ workers (not Celery), no auth. Sync FastAPI by default; async
> only at the SSE endpoint.

## Overview

FastAPI orchestrates a per-repo pipeline. ARQ workers run long-running stages
(clone, repro, Codex). SQLite (WAL mode) stores everything. The frontend polls
REST endpoints + subscribes to SSE for live runs.

```
┌──────────────────────────────────────────────────┐
│                  Next.js Frontend                │
└─────────────┬────────────────┬───────────────────┘
              │ REST           │ SSE (live runs)
              ↓                ↓
┌──────────────────────────────────────────────────┐
│              FastAPI (sync layer)                │
│  - validation, CRUD                              │
│  - enqueues ARQ jobs (or runs inline if no Redis)│
│  - SSE endpoint reads from Redis pubsub          │
└─────────────┬────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────────────────┐
│              ARQ Workers                          │
│  - HealthScorer, Profiler, CodeMapper            │
│  - PRPatternAnalyzer, NoBrainerScanner           │
│  - IssueScorer, ReproEngine, CodexRunner         │
│  - Guardrails, CommentPlanner, PRWriter          │
│  - TractionScorer, StrategyAdapter               │
│  - publishes log events to Redis pubsub          │
└─────────────┬─────────────────┬──────────────────┘
              │                 │
              ↓                 ↓
       ┌──────────┐      ┌─────────────┐
       │ SQLite   │      │ Redis       │
       │  (state) │      │ (queue+pub) │
       └──────────┘      └─────────────┘
              │
              ↓
       ┌──────────────────────────────┐
       │ Sandbox (subprocess)         │
       │  - clone, install, test      │
       │  - Codex CLI                 │
       │  - git push, gh PR           │
       └──────────────────────────────┘
```

## Module Map

```
app/
├── main.py                          # FastAPI entry
├── config.py                        # settings (env, secrets)
├── log_bus.py                       # Redis pubsub + log persistence
├── seed.py                          # alembic upgrade + single-user seed
├── db/
│   ├── session.py                   # SQLAlchemy engine + WAL pragmas
│   └── models.py                    # all ORM models
├── api/
│   ├── auth.py                      # /auth/me single-user shim
│   ├── repos.py
│   ├── issues.py
│   ├── prs.py
│   ├── runs.py                      # incl. /runs/:id/stream (SSE — only async route)
│   ├── metrics.py
│   ├── strategy.py
│   ├── settings.py
│   ├── nobrainers.py
│   └── activity.py
├── schemas/                         # Pydantic request/response
├── services/                        # health_scorer, profiler, code_mapper,
│                                    # pr_pattern_analyzer, no_brainer_scanner,
│                                    # issue_scorer, repro_engine,
│                                    # codex_runner, codex_pipeline, guardrails,
│                                    # comment_planner, pr_writer, git_ops,
│                                    # validator, traction_scorer, strategy_adapter
├── pipeline/
│   ├── orchestrator.py              # state-machine driver
│   ├── stages.py                    # stage names + timeouts
│   ├── queue.py                     # enqueue_run + ARQ/inline dispatch
│   ├── worker.py                    # ARQ WorkerSettings
│   └── traction_worker.py           # poll_traction (cron)
├── sandbox/
│   ├── runner.py                    # subprocess + timeout
│   ├── stack_detector.py
│   └── validators.py
└── utils/                           # crypto, slug, repo_url, redis_client, logging
```

## Two Pipeline Types

### A. Repo Onboarding Pipeline

Runs on `POST /repos` (or `POST /repos/:id/rescan`).

```
fetch_metadata → score_health → fetch_profile → build_code_map
  → analyze_pr_patterns → scan_no_brainers → detect_issues → done
```

### B. Issue Fix Pipeline

```
reproduce → plan_fix → generate_patch → validate → guardrail
  → push_branch → post_comment → open_pr → schedule_traction → done
```

### B'. No-Brainer Fix Pipeline

```
prepare → generate_patch → guardrail → push_branch → open_pr → schedule_traction → done
```

## Sync vs Async

| Endpoint | Sync/Async |
|---|---|
| Add repo, get repo, get issues, get PRs, get metrics | Sync |
| Trigger rescan, retry issue, approve no-brainer | Sync API → enqueue ARQ job → return run_id |
| Stream run logs | **Async only** — SSE endpoint, Redis pubsub |
| All Codex / clone / sandbox work | ARQ worker (or inline thread fallback) |

## State Persistence

Every pipeline stage writes:
1. **Stage start** — set `pipeline_runs.stage` + emit log event
2. **Stage progress** — log events to Redis pubsub + persist in `log_events`
3. **Stage end** — update `pipeline_runs.status` (`succeeded` / `failed` /
   `abandoned` / `cancelled`)

If an ARQ worker crashes mid-stage, an orphan `running` row stays. (Future
work: a beat job to scan for orphans older than max stage timeout.)

## Concurrency

- One pipeline at a time per repo (Redis lock by `repo_id`)
- Up to N parallel pipelines across different repos (env: `MAX_CONCURRENT_RUNS`,
  default 3)

## Working Directory

Per-repo, not per-run (per `DECISIONS.md`). One clone at
`$WORKDIR/repos/<repo_id>/`. Redis lock per `repo_id` for any git op.

## Error Handling

See `policies/failure_modes.md`. Defaults:

- **Transient** (network, rate limit) → exponential backoff, max 3 retries
- **Permanent** (invalid repo, fork mismatch) → fail fast, surface to UI
- **Codex errors** → 2 retries with shrunk scope, then abandon issue
- **Validation failures** → retry patch generation up to 2 times, then abandon

## No auth

Per `DECISIONS.md`: single-user local app. A user row is seeded at startup if
the `users` table is empty. All endpoints are open. Don't expose this on a
public network.
