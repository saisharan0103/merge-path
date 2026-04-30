# AGENTS.md

Universal instructions for any coding agent (Claude Code, Cursor, Aider, Codex, etc.) working in this repo.

> Claude Code: see `CLAUDE.md` for the same content with Claude-specific framing. Both files are kept in sync.

## Project

Autonomous OSS contribution agent. Picks reproducible issues from public GitHub repos, generates fixes via Codex CLI, opens PRs from a user fork to upstream, tracks traction, adapts strategy. Single-user, self-hosted, v1.

## Spec lives in `build_docs/`

Read order: `prd/PRD.md` → `specs/01_architecture.md` → `data/DATA_MODEL.md` → `api/API_CONTRACT.md` → other specs as relevant.

**The spec is canonical.** If a task conflicts with it, surface the conflict before coding.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async, Alembic |
| Queue | Celery + Redis |
| DB | PostgreSQL 15+ |
| Frontend | Next.js, React, TypeScript, Tailwind, Recharts |
| Code agent | Codex CLI (subprocess) |
| GitHub | PyGithub + raw REST |

## Commands

```bash
# Backend
poetry install
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A app.pipeline.tasks worker --loglevel=info
celery -A app.pipeline.tasks beat --loglevel=info
pytest -x
pytest --cov=app --cov-report=term-missing
ruff check .
mypy app/

# Frontend
pnpm install
pnpm dev
pnpm test
pnpm typecheck
pnpm lint
pnpm build

# Full stack
docker compose up
```

## Layout

```
app/             # FastAPI backend (api, schemas, db, services, pipeline, sandbox, utils)
web/             # Next.js frontend (app, components, lib)
build_docs/      # canonical specs — read before non-trivial changes
tests/           # pytest
```

## Conventions

- **One PR = one problem.** No unrelated cleanup.
- **No new dependencies** without explicit justification.
- **Match existing style.** No drive-by reformatting.
- **Backend is async.** No sync DB calls in request handlers.
- **GitHub calls** go through `services/github_client.py` only.
- **Secrets** (PATs, JWT secret) never logged, never committed. Use `app/utils/crypto.py` for at-rest encryption.
- **Migrations** ship with every schema change. Never edit a committed migration.
- **Type hints required** on all public functions in `services/`.
- **Tests required** for new service modules, bug fixes, new endpoints.
- **Use structured logger.** No `print()`.

## Load-bearing details (don't break)

1. **Two-URL repo model** — every `Repository` has both `upstream_url` (issues + PR target) and `fork_url` (where branches push). Verified on add. See `specs/04_fork_pr_strategy.md`.
2. **Pipeline state machine** — runs go through `pending → running → succeeded|failed|abandoned|cancelled`. Cancel uses a flag checked at safe points. See `specs/02_pipeline_state_machine.md`.
3. **Codex subprocess wrapper** — single entry point in `services/codex_runner.py`. Don't bypass.
4. **Reproduction confidence ≥ 0.7** required to comment/PR. Below that → skip silently.
5. **SSE for live logs, polling for lists.** Don't add WebSockets. See `specs/05_log_streaming.md`.
6. **Buffer + traction logic** — `buffer_until = now + median_review × 2`, min 7d, max 21d, +5d grace. Don't change without updating spec.

## Failure handling

Catalogued in `build_docs/policies/failure_modes.md`. Use those documented actions, not ad-hoc handling.

## Done means

- Tests + lint + types pass
- Migration applied if schema changed
- Relevant `build_docs/checklists/acceptance_criteria.md` items still hold
- For full features: `build_docs/checklists/done_checklist.md` satisfied

## Don't

- Commit `.env` or any PAT
- Post real GitHub comments/PRs from local dev (use a sandbox repo)
- Change buffer/traction math without updating the spec
- Add a parallel code-agent path; extend `CodeAgentRunner` interface instead
- Break the classic theme on frontend (PRD §9 tokens)
