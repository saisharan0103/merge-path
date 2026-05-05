# DECISIONS.md

Locked decisions for this project. **Read this before changing anything in `build_docs/`.**

If a decision here conflicts with a `build_docs/` spec, this file wins. Specs that disagree must be updated.

---

## Stack

| Concern | Decision |
|---|---|
| Backend language | **Python 3.11+** |
| Backend framework | **FastAPI** |
| Concurrency | **Sync by default**, async **only** at SSE endpoint (`/runs/:id/stream`) |
| Database | **SQLite** with WAL mode (single-user local app) |
| ORM | SQLAlchemy + Alembic |
| Background jobs | **ARQ** (not Celery) |
| Job broker | Redis (via Docker on Windows) |
| Frontend | **Next.js + React + TypeScript + Tailwind** in `web/` |
| Charts | Recharts |
| Code agent | **Codex CLI via official Python SDK** (`openai-codex-sdk` / `codex_app_server`); subprocess fallback |
| GitHub | PyGithub + raw REST where needed |
| Sandbox | Plain subprocess (no Docker) |

## SQLite-specific adaptations

Spec was written assuming Postgres. These translate cleanly to SQLite:

| Spec uses | SQLite substitution |
|---|---|
| `JSONB` columns | `JSON` (TEXT) via SQLAlchemy `JSON` type |
| `TEXT[]` arrays | JSON-encoded list via SQLAlchemy `JSON` |
| Postgres advisory locks | **Redis locks** (`redis.lock(f"repo:{id}", ...)`) |
| `BIGSERIAL` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| ENUM types | TEXT with `CHECK` constraint |
| `SELECT FOR UPDATE` | Redis lock around the critical section |

**Mandatory SQLite settings** in `app/db/session.py`:

```python
PRAGMA journal_mode=WAL
PRAGMA synchronous=NORMAL
PRAGMA busy_timeout=30000
PRAGMA foreign_keys=ON
```

Without WAL, Celery/ARQ workers and FastAPI will deadlock on the file.

## Schema decisions

- **Drop** `RepositoryConfig` table.
  - `auto_pr_enabled` → invert into `repositories.paused`
  - `allowed_labels`, `max_files_changed`, etc. → `contribution_rules` rows with `scope='repo'`
  - Empty table = just drop. Skip data migration.
- **Two-URL repo model** is mandatory. `repositories` has both `upstream_url` and `fork_url` columns. Old `repo_url` column is dropped. Old single-URL `POST /repos` endpoint breaks.
- **Drop `init_db.create_all`.** Replace with Alembic from migration `0001_initial`.

## Authentication

**No auth. Period.**

- No JWT, no login, no bearer tokens
- No dev/prod split
- Single user is seeded at startup if `users` table is empty
- All endpoints are open — this is a local-only single-user app
- Remove any JWT/auth references from the spec when implementing

If a spec file mentions JWT, ignore it. The CLAUDE.md / AGENTS.md / acceptance criteria should be updated to drop "Auth" sections during implementation.

## Frontend

- **Rip out `app/ui.py`** at start of build. Backend serves API only.
- Single frontend lives in `web/` (Next.js).
- Classic theme tokens (cream `#FAF8F3` bg, serif headings, dense tables) per `prd/PRD.md` §9.

## PAT storage

- **Env fallback first.** Read `GITHUB_TOKEN` from env if `users.github_pat_encrypted` is null.
- **DB override second.** If user saves a PAT via UI, it goes encrypted into `users.github_pat_encrypted` and overrides env.
- Encryption: AES-GCM via `app/utils/crypto.py` with `ENCRYPTION_KEY` from env.

## Issue filtering

- **Discard the current hardcoded label allowlist** (`{good first issue, help wanted, bug, documentation}`).
- Use the spec's full scoring model (0–100 score + `eligibility_verdict` + `filter_reason`).
- A cheap label pre-gate is fine as a first-pass reject filter, but don't gate solely on labels.

## Health scorer

**Two-pass** to keep "Add Repo" responsive:

- **Fast signals (synchronous-ish, < 5s):** last_commit_at, open_pr_count, merged_pr_count_30d, release_count_180d
- **Slow signals (async follow-up):** median_review_hours, ci_pass_rate, maintainer_response_rate, external_merge_rate, active_contributors_90d
- Cache aggressively: 24h TTL on health rows.

Verdict can be set after fast pass; refined after slow pass.

## No-brainer detection

**LLM judgment, not heuristics.** Each detection type (missing_env_docs, broken_link, etc.) routes through Codex SDK with a focused prompt. Worth the cost for accuracy.

## PR pattern title detection

4 hardcoded regex patterns + plain fallback:

1. `^(\w+)\(([^)]+)\):\s+(.+)$` → conventional commit (`fix(scope): desc`)
2. `^\[([^\]]+)\]\s+(.+)$` → bracket prefix (`[scope] desc`)
3. `^(.+)\s+\(#\d+\)$` → trailing issue ref (`desc (#123)`)
4. `^(.+)$` → plain

If any one matches >40% of merged PR titles, lock it as the repo's pattern. Else "plain."

## Reproduction confidence

**Boolean 5-checkbox, not weighted float.** Issue is "reproduced" if **all 5** pass:

1. Reproduction script runs to completion (no setup error)
2. It produces an error / failure / wrong output
3. Error matches issue: same exception class **OR** same error message substring **OR** same observable behavior
4. Error originates from a file in repo's source tree (not deps, not test fixtures)
5. 3/3 reruns produce the same error (deterministic)

**All 5 pass → proceed. Otherwise → skip silently.** No comment, no PR.

The float `confidence = checks_passed / 5` is for UI display only; gate on the boolean.

For check #3, use regex/substring matching first. LLM judgment only as fallback.

## Working directory

**Per-repo clone, not per-run.**

- One clone per repo at `$WORKDIR/repos/<repo_id>/`
- Redis lock per `repo_id` for any git operation
- Concurrent runs on different repos are fine; same repo is serialized
- Update `specs/01_architecture.md` and `specs/04_fork_pr_strategy.md` accordingly

## Codex CLI integration

**Use the official Python SDK** (`openai-codex-sdk` / `codex_app_server`).

```python
from codex_app_server import Codex, AsyncCodex

with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.4")
    result = thread.run(prompt, output_schema=fix_plan_schema)
```

- Wrap behind `services/codex_runner.py` so subprocess fallback (`codex exec --json --sandbox workspace-write`) is a one-line swap
- Use `output_schema` parameter for structured fix plans (replaces parsing `fix_plan.json` from disk)
- Sandbox mode: `workspace-write` (allow file edits, no network for the patch stage)
- Capture diff via `git diff` after thread completes
- `CODEX_FAKE_MODE=true` env flag returns canned diffs for testing without burning real Codex calls

User installs once: `npm install -g @openai/codex` + `codex login` + `pip install openai-codex-sdk`.

## Sandbox

- Plain `subprocess.run` with timeout
- No Docker, no namespace isolation
- Single-user trust model — user controls what runs
- Add containerization only if multi-tenant (never, per current scope)

## Spec drift to update during build

These specs were written before all decisions locked. Update them as you go:

- `specs/01_architecture.md` — Celery → ARQ, Postgres → SQLite, sync default
- `specs/02_pipeline_state_machine.md` — keep as-is, applies to ARQ same as Celery
- `specs/03_codex_integration.md` — rewrite around Python SDK with subprocess fallback
- `specs/04_fork_pr_strategy.md` — clone is per-repo not per-run
- `specs/05_log_streaming.md` — keep as-is
- `data/DATA_MODEL.md` — Postgres-isms → SQLite (JSONB → JSON, TEXT[] → JSON list); drop RepositoryConfig; add note on Redis locks
- `api/API_CONTRACT.md` — drop all auth endpoints and `Authorization` header requirements; users table seeded at startup
- `prd/PRD.md` — drop JWT line in §13 risks; update §6 to two-URL model (already correct)
- `checklists/acceptance_criteria.md` — drop section A (Auth & Settings → Settings only); update repo add to two-URL
- All prompt templates — keep as-is, they're tool-agnostic

Update specs in-place. Don't leave stale instructions for future Claude Code sessions to misread.

## Build approach

**One shot, not phased.** Build the whole thing in a single Claude Code session with internal sanity checkpoints (run tests after each major module). Do not stop and ask for permission between phases. The handoff prompt covers this.
