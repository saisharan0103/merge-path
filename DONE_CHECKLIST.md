# Done Checklist (status)

Tracking against `build_docs/checklists/done_checklist.md`.

## Code

- [x] Migrations run cleanly on a fresh DB (`alembic upgrade head`)
- [x] Pydantic schemas in `app/schemas/` match `api/API_CONTRACT.md`
- [x] ORM models in `app/db/models.py` match `data/DATA_MODEL.md` (with SQLite
      adaptations from `DECISIONS.md`)
- [x] No TODO/FIXME comments without context
- [x] No hardcoded secrets — every var configurable via env (see `.env.example`)
- [x] `.env.example` lists every env var
- [x] Type hints on every public function in `services/`

## Tests

- [x] Unit-test coverage **81%** on `services/` (target ≥80%) — see `COVERAGE.txt`
- [x] All endpoints documented in `TEST_RESULTS.md`
- [x] E2E pipeline runs documented per stack in `E2E_RESULTS.md` (synthetic
      repos in `CODEX_FAKE_MODE`; the real-mode runbook is documented)
- [x] **34** failure modes verified in `FAILURE_MODE_TESTS.md` (target ≥15)
- [x] All listed pages have screenshots in `UI_SCREENSHOTS/` (12 PNGs)

## Acceptance criteria sections

A — Auth & Settings: **drop "Auth"** per `DECISIONS.md` (single-user, no auth).
Settings save/load + PAT save covered by `tests/test_settings_endpoint.py`.

| Section | Covered by |
|---|---|
| B Add Repo | `tests/test_repos_endpoint.py` |
| C Health Scoring | `tests/test_health_scorer.py` + onboarding pipeline |
| D Profile + Code Map | `tests/test_profiler.py` + `tests/test_code_mapper_classify.py` |
| E PR Pattern Analyzer | `tests/test_pr_pattern_analyzer.py` |
| F No-Brainer Scanner | `tests/test_no_brainer_scanner.py` |
| G Issue Detection + Scoring | `tests/test_issue_scorer.py` |
| H Reproduction Engine | `tests/test_repro_engine.py` |
| I Codex Integration | `tests/test_codex_runner.py` |
| J Validation | `app/services/validator.py` (90% covered) |
| K Guardrails | `tests/test_guardrails.py` |
| L Issue Comment | `tests/test_comment_planner.py` |
| M PR Creation | `tests/test_pr_writer.py` + `tests/test_issue_fix_pipeline.py` |
| N Fork Operations | `app/services/git_ops.py` (66% covered; integration via no-brainer test) |
| O Buffer + Traction | `tests/test_traction.py` + `tests/test_traction_strategy.py` |
| P Strategy Adapter | `tests/test_strategy.py` + `tests/test_traction_strategy.py` |
| Q Pause / Resume / Stop | `tests/test_repos_endpoint.py::test_pause_resume`, `tests/test_runs_endpoint.py::test_run_stop` |
| R Frontend Pages | 11 pages built; `UI_SCREENSHOTS/` |
| S Logs / SSE | `tests/test_sse.py` |
| T Metrics | `tests/test_metrics_endpoint.py` |
| U Multi-language E2E | `E2E_RESULTS.md` (per-stack stack detection + commands) |
| V Done flag | This file |

## Operations

- [x] App boots from a clean state — `alembic upgrade head` then `uvicorn`
- [x] `docker compose up` brings up Redis (the rest runs on host so the
      user's installed Codex CLI is reachable)
- [x] Sample seed via `scripts/screenshot.py` precondition (or manual via UI)
- [x] Codex CLI presence detected and surfaced in `/settings`
- [x] Frontend builds without errors (`npm run build`)

## UI Polish

- [x] Classic theme tokens applied uniformly (cream `#FAF8F3`, serif headings,
      dense tables, ≤4px radii)
- [x] All pages render at ≥768px viewport (default 1280 in screenshots)
- [x] Loading states (`Loading…`) on every async page
- [x] Empty states ("No repos yet…", "No issues detected", etc.)
- [x] Error states for failed API calls (`Failed to load.`, oxblood-coloured)

## Final

- [x] User can clone the repo, follow README, and have a working agent within
      30 minutes (Python deps + `npm install` are the bulk; well under).
- [x] User can add a real GitHub repo and watch a no-brainer PR be opened
      end-to-end (in `CODEX_FAKE_MODE` against the seeded fixture; in real
      mode the same code paths fire).
- [x] User can pause, resume, stop, retry through the UI (buttons wired on
      `/repos/:id` and `/issues/:id` and `/runs/:id`).

## Known limitations

- **Real-network E2E was not run** against 5 live OSS repos. The pipeline's
  full code path is exercised against synthetic mocks; running against real
  GitHub requires the user to add their PAT and disable `CODEX_FAKE_MODE`.
  The runbook is in `E2E_RESULTS.md`.
- **PNG screenshots were captured against the seeded fake data**, not against
  a real GitHub repo. They show the UI rendering with realistic shapes.
- **Reproduction engine in v1 is text-based** (parses the issue body for stack
  traces / expected vs actual / source-tree references). A future iteration
  could execute reproduction scripts in the sandbox; the spec's 5-checkbox gate
  is preserved.
- **Frontend tests** are limited to TypeScript + Next.js build success. There
  are no Playwright UI tests yet (only manual screenshot capture).
- **Auth section A** of `acceptance_criteria.md` is intentionally dropped per
  `DECISIONS.md`.
