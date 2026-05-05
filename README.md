# PatchPilot

Autonomous OSS contribution agent. Scores GitHub repos, learns merge culture,
picks reproducible issues, generates fixes via Codex CLI, opens PRs from a
user-owned fork to upstream, tracks traction, adapts strategy.

**Single user. Self-hosted. Local-first.**

The full design is in [`build_docs/`](./build_docs/) — start with
[`prd/PRD.md`](./build_docs/prd/PRD.md) and the locked decisions in
[`DECISIONS.md`](./DECISIONS.md).

---

## What it does

1. You give it a GitHub repo (upstream URL + your fork URL)
2. It scores repo health, builds a code map, learns the repo's PR conventions
3. Detects no-brainer doc fixes (missing env docs, no troubleshooting, etc.)
4. Picks reproducible issues, scores them 0–100
5. Reproduces locally; if all 5 boolean checks pass, plans + generates a fix via Codex
6. Validates against the repo's own tests, runs guardrails, opens a fork→upstream PR
7. Polls traction every 30 minutes; adapts per-repo strategy (green/yellow/red/blacklist)

Everything is visible in an 11-page Next.js UI with a deliberate "classic" theme
(cream background, serif headings, dense tables — see PRD §9).

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI (sync default, async at SSE only) |
| DB | SQLite with WAL mode |
| ORM | SQLAlchemy + Alembic |
| Background jobs | ARQ (Redis broker) |
| Frontend | Next.js + React + TypeScript + Tailwind |
| Charts | Recharts |
| Code agent | Codex CLI via subprocess (`CODEX_FAKE_MODE` for tests) |
| GitHub | httpx + raw REST |

## Prerequisites

- Python 3.11+
- Node 18+
- Redis (for log pubsub + the ARQ worker; optional for local dev — the app
  falls back to `fakeredis` and inline pipeline execution if Redis is unavailable)
- Codex CLI (only required for real-mode runs; install with
  `npm install -g @openai/codex` then `codex login`. Tests run with
  `CODEX_FAKE_MODE=true` and need none of this.)

## Install

```bash
git clone <this-repo>
cd merge-path

# backend
python -m venv .venv
source .venv/Scripts/activate     # or `.venv\Scripts\Activate.ps1` on PowerShell
pip install -r requirements.txt
cp .env.example .env

alembic upgrade head              # creates the schema

# frontend
cd web
npm install
cd ..
```

## Run (dev)

In three terminals:

```bash
# 1. Backend (FastAPI)
uvicorn app.main:app --reload --port 8000

# 2. Worker (ARQ) — optional; without it, runs execute inline
arq app.pipeline.worker.WorkerSettings

# 3. Frontend (Next.js)
cd web && npm run dev      # → http://localhost:3000
```

Open <http://localhost:3000>. Click **Add repo** in the top right of the
Repositories page. Enter both URLs. The agent will verify the fork-of-upstream
relationship, then onboard automatically.

## Run (with Docker Compose)

```bash
docker compose up
```

Brings up Redis. Backend + worker + frontend run on the host (Codex CLI must
be installed there anyway, so we don't containerize them by default).

## Test

```bash
pytest                                   # 139 tests
pytest --cov=app/services                # 81% coverage on services
ruff check .                             # lint
mypy app/                                # types

# frontend
cd web && npm run typecheck && npm run build
```

## Configuration

Every env var is documented in [`.env.example`](./.env.example). Highlights:

- `GITHUB_TOKEN` — fallback PAT used when the user hasn't saved one in the UI
- `ENCRYPTION_KEY` — 32-byte base64 key for at-rest PAT encryption (auto-generated
  on first run if absent)
- `CODEX_FAKE_MODE=true` — return canned diffs (default; flip to `false` for
  real Codex calls)
- `BUFFER_MULTIPLIER=2.0` — `buffer_until = median_review_hours × multiplier`
  (clamped to [7d, 21d]; +5d grace)

## Repo layout

```
app/                  FastAPI backend
  api/                routes
  schemas/            Pydantic req/res
  db/                 models + session
  services/           business logic
  pipeline/           orchestrator + ARQ worker
  sandbox/            subprocess + per-stack validators
  utils/              crypto, slug, redis, logging
alembic/              migrations
build_docs/           full spec
tests/                pytest
web/                  Next.js frontend
scripts/              ops scripts (screenshot.py)
UI_SCREENSHOTS/       per-page PNGs
```

## Key design rules (from `CLAUDE.md`)

1. One PR = one problem. No drive-by changes.
2. Async only at the SSE endpoint. Everything else is sync FastAPI.
3. PAT and secrets — never log, never commit. Use `app/utils/crypto.py`.
4. Reproduction confidence < 0.7 → skip silently. No comment, no PR.
5. The two-URL repo model is load-bearing. PRs go fork→upstream; issues are read from upstream.

## Artifacts

- [`TEST_RESULTS.md`](./TEST_RESULTS.md) — every endpoint, sample req/res
- [`E2E_RESULTS.md`](./E2E_RESULTS.md) — pipeline runs against synthetic repos for 5 stacks
- [`FAILURE_MODE_TESTS.md`](./FAILURE_MODE_TESTS.md) — 34 failure modes verified
- [`COVERAGE.txt`](./COVERAGE.txt) — line coverage (81% on services)
- [`UI_SCREENSHOTS/`](./UI_SCREENSHOTS/) — PNG of every page

## Authentication

There is no authentication. This is a single-user local app per
[`DECISIONS.md`](./DECISIONS.md). Don't expose it on a public network.
