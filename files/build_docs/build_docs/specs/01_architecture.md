# Architecture Spec

## Overview

FastAPI backend orchestrates a pipeline of stages per repo. Celery workers run long-running stages (clone, repro, Codex). Postgres stores everything. Frontend polls REST endpoints + subscribes to SSE for live runs.

```
┌──────────────────────────────────────────────────┐
│                  Next.js Frontend                │
└─────────────┬────────────────┬───────────────────┘
              │ REST           │ SSE (live runs)
              ↓                ↓
┌──────────────────────────────────────────────────┐
│              FastAPI (sync layer)                │
│  - auth, validation, CRUD                        │
│  - enqueues Celery jobs                          │
│  - SSE endpoint reads from Redis pubsub          │
└─────────────┬────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────────────────┐
│            Celery Workers (async layer)          │
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
       │ Postgres │      │ Redis       │
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
├── db/
│   ├── session.py                   # async SQLAlchemy session
│   └── models.py                    # all ORM models
├── api/
│   ├── deps.py                      # auth dependency
│   ├── repos.py                     # /repos endpoints
│   ├── issues.py                    # /issues endpoints
│   ├── prs.py                       # /prs endpoints
│   ├── runs.py                      # /runs + /runs/:id/stream (SSE)
│   ├── metrics.py                   # /metrics/*
│   ├── strategy.py                  # /strategy/*
│   └── settings.py                  # /settings
├── schemas/                         # Pydantic request/response
│   ├── repo.py
│   ├── issue.py
│   ├── pr.py
│   ├── run.py
│   └── ...
├── services/
│   ├── github_client.py             # PyGithub wrapper + retry
│   ├── health_scorer.py
│   ├── profiler.py
│   ├── code_mapper.py
│   ├── pr_pattern_analyzer.py
│   ├── no_brainer_scanner.py
│   ├── issue_scorer.py
│   ├── repro_engine.py
│   ├── codex_runner.py
│   ├── guardrails.py
│   ├── comment_planner.py
│   ├── pr_writer.py
│   ├── traction_scorer.py
│   └── strategy_adapter.py
├── pipeline/
│   ├── orchestrator.py              # state machine driver
│   ├── stages.py                    # stage definitions
│   └── tasks.py                     # Celery task defs
├── sandbox/
│   ├── runner.py                    # subprocess + timeout
│   ├── stack_detector.py            # detect Python/Node/Go/Rust/Java
│   └── validators.py                # per-stack test/lint/build
├── log_bus.py                       # Redis pubsub publisher
└── utils/
    ├── crypto.py                    # PAT encryption
    └── slug.py                      # branch name slugify
```

## Two Pipeline Types

### A. Repo Onboarding Pipeline
Runs once per repo when added (re-runs on `/rescan`).

```
add_repo
  → fetch_metadata
  → score_health
  → if green/yellow:
      → fetch_profile
      → build_code_map
      → analyze_pr_patterns
      → scan_no_brainers
      → detect_issues
  → if red: stop, persist verdict
```

All stages are Celery jobs chained via Celery `chain()`. Each stage updates `pipeline_runs.status` and emits log events.

### B. Issue Fix Pipeline
Runs per selected issue.

```
pick_issue
  → reproduce
  → if confidence < 0.7: abandon
  → plan_fix (Codex)
  → generate_patch (Codex)
  → validate (run tests)
  → if validation fails (≤2 retries): retry generate_patch
  → guardrail_check
  → push_branch_to_fork
  → post_issue_comment
  → open_pull_request (fork → upstream)
  → schedule_traction_check (after buffer_until)
```

## Sync vs Async

| Endpoint | Sync/Async |
|---|---|
| Add repo, get repo, get issues, get PRs, get metrics | Sync, fast DB read |
| Trigger rescan, retry issue, run no-brainer | Sync API → enqueue Celery job → return run_id |
| Stream run logs | SSE endpoint, holds connection, reads Redis pubsub |
| All Codex / clone / sandbox work | Async (Celery) |

## State Persistence

Every pipeline stage writes:
1. **Stage start** — insert row in `agent_runs` (status=`running`)
2. **Stage progress** — log events to Redis pubsub + persist in `log_events`
3. **Stage end** — update `agent_runs.status` (`succeeded` / `failed` / `abandoned`)

If worker crashes mid-stage, orphan runs are detected by a Celery beat job that scans for `running` runs older than stage timeout and marks them `failed`.

## Concurrency

- One repo onboarding pipeline at a time per repo (Postgres advisory lock by `repo_id`)
- Up to N parallel issue fix pipelines (configurable, default 3)
- Up to M parallel repos in onboarding (default 5)

## Error Handling

See `policies/failure_modes.md` for the full catalog.

Default policy:
- **Transient errors** (network, rate limit) → exponential backoff, max 3 retries
- **Permanent errors** (invalid repo, fork mismatch) → fail fast, log, surface to UI
- **Codex errors** → 2 retries with shrunk scope, then abandon issue
- **Validation failures** → retry patch generation up to 2 times, then abandon
