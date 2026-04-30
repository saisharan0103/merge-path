# CLAUDE.md

Instructions for Claude Code working in this repo.

## What this is

An autonomous OSS contribution agent. Scores GitHub repos, learns merge culture, picks reproducible issues, generates fixes via Codex CLI, opens PRs from a user-owned fork to upstream, tracks traction, adapts strategy.

**Single user, self-hosted, v1.**

## Build spec is canonical

Full spec lives in `build_docs/`. **Read it before changing anything non-trivial.**

Reading order:
1. `build_docs/prd/PRD.md` — what + why
2. `build_docs/specs/01_architecture.md` — system shape
3. `build_docs/data/DATA_MODEL.md` — schema
4. `build_docs/api/API_CONTRACT.md` — endpoints
5. Other specs as needed

If a request conflicts with the spec, **flag it before changing code**. Do not silently deviate.

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), Alembic
- **Queue:** Celery + Redis
- **DB:** PostgreSQL 15+
- **Frontend:** Next.js + React + TypeScript + Tailwind
- **Charts:** Recharts
- **Code agent:** Codex CLI (subprocess wrapper, see `specs/03`)
- **GitHub:** PyGithub + raw REST where needed

## Commands

```bash
# Backend (from /app)
poetry install
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Worker
celery -A app.pipeline.tasks worker --loglevel=info
celery -A app.pipeline.tasks beat --loglevel=info

# Tests
pytest -x
pytest --cov=app --cov-report=term-missing

# Lint / type
ruff check .
mypy app/

# Frontend (from /web)
pnpm install
pnpm dev
pnpm test
pnpm typecheck
pnpm lint
pnpm build

# Full stack
docker compose up
```

## Repo layout

```
app/                 # FastAPI backend
  api/               # routes (one file per resource)
  schemas/           # Pydantic req/res
  db/                # models, session
  services/          # business logic (one module per concern)
  pipeline/          # Celery tasks + state machine
  sandbox/           # subprocess + per-stack validators
  utils/
web/                 # Next.js frontend
  app/               # routes
  components/
  lib/
build_docs/          # specs (read these)
tests/               # pytest
```

## Hard rules

1. **One PR = one problem.** No drive-by changes. No "while I was here" cleanup.
2. **No new deps without justification.** If you need one, pause and explain why.
3. **Match existing style.** Don't reformat lines you didn't need to touch.
4. **Async everywhere on backend.** No sync DB calls inside FastAPI handlers.
5. **All external calls go through `services/github_client.py`.** Never call PyGithub directly elsewhere.
6. **PAT and secrets:** never log, never commit. Use `app/utils/crypto.py` for at-rest encryption.
7. **Migrations:** every schema change ships with an Alembic migration. Never edit a committed migration.
8. **Tests required for:** new service modules, bug fixes, new endpoints.
9. **Type hints required** on all public functions in `services/`.
10. **No `print()`** — use the structured logger.

## Things that look easy but aren't

- The two-URL repo model (`upstream_url` + `fork_url`) is load-bearing. Never collapse them. PRs go fork→upstream; issues are read from upstream. See `specs/04`.
- The pipeline state machine (`specs/02`) handles cancel/pause/retry. New stages must integrate with it, not bypass it.
- Codex calls run in a subprocess with timeout + scope allowlist. See `specs/03`. Don't add a second invocation path.
- Reproduction confidence < 0.7 means **skip silently** — no comment, no PR. This is a safety rule, not a config.
- SSE endpoint reads from Redis pubsub + replays last 200 logs from DB on connect. See `specs/05`. Don't add WebSockets.

## When stuck

1. Re-read the relevant `build_docs/specs/*.md`
2. Check `build_docs/policies/failure_modes.md` for the documented handling
3. Check `build_docs/checklists/acceptance_criteria.md` for the expected behavior
4. If still unclear, ask before guessing

## Definition of done

A change isn't done until:
- Tests pass (`pytest -x`)
- Lint passes (`ruff check .`)
- Types pass (`mypy app/`)
- Migration applied if schema changed
- Relevant section in `build_docs/checklists/acceptance_criteria.md` still holds
- For full features: `build_docs/checklists/done_checklist.md` items checked

## Don't

- Don't commit `.env` or any PAT
- Don't post real GitHub comments/PRs from local dev unless explicitly testing E2E (use a sandbox repo)
- Don't change buffer/traction math without updating spec
- Don't add a code agent alternative (Aider etc.) without going through the `CodeAgentRunner` interface
- Don't break the classic theme on frontend (see PRD §9)
