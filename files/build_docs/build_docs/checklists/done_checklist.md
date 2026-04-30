# Done Checklist

This is the **final gate** before handing back to the user. Every box must be checked. Every artifact must exist and be referenced from this file.

Do not declare "done" without producing all of these.

## Code

- [ ] All migrations run cleanly on a fresh database (`alembic upgrade head` or equivalent)
- [ ] All Pydantic schemas in `app/schemas/` match `api/API_CONTRACT.md`
- [ ] All ORM models in `app/db/models.py` match `data/DATA_MODEL.md`
- [ ] No TODO/FIXME comments in service code without a tracking issue
- [ ] No hardcoded secrets — all configurable via env
- [ ] `.env.example` lists every env var the app reads
- [ ] Type hints on every public function in `services/`

## Tests (per `checklists/testing_requirements.md`)

- [ ] Unit test coverage ≥ 80% on `services/` (`COVERAGE.txt` attached)
- [ ] All endpoints have entries in `TEST_RESULTS.md` with sample req/res
- [ ] E2E run against 5 real repos (one per stack) documented in `E2E_RESULTS.md`
- [ ] At least 15 failure modes verified in `FAILURE_MODE_TESTS.md`
- [ ] All listed pages have screenshots in `UI_SCREENSHOTS/`

## Acceptance criteria (per `checklists/acceptance_criteria.md`)

Every box in `acceptance_criteria.md` sections A through V is checked.

- [ ] Section A — Auth & Settings
- [ ] Section B — Add Repo
- [ ] Section C — Health Scoring
- [ ] Section D — Profile + Code Map
- [ ] Section E — PR Pattern Analyzer
- [ ] Section F — No-Brainer Scanner
- [ ] Section G — Issue Detection + Scoring
- [ ] Section H — Reproduction Engine
- [ ] Section I — Codex Integration
- [ ] Section J — Validation
- [ ] Section K — Guardrails
- [ ] Section L — Issue Comment
- [ ] Section M — PR Creation
- [ ] Section N — Fork Operations
- [ ] Section O — Buffer + Traction
- [ ] Section P — Strategy Adapter
- [ ] Section Q — Pause / Resume / Stop
- [ ] Section R — Frontend Pages
- [ ] Section S — Logs / SSE
- [ ] Section T — Metrics
- [ ] Section U — Multi-language E2E

## Observability

- [ ] Every Celery task logs start, end, duration, errors
- [ ] Every API endpoint logs request method, path, user_id, status, duration
- [ ] Errors include enough context for debugging (no bare `except Exception: pass`)

## Documentation

- [ ] Top-level `README.md` explains: what the app does, how to run, how to test, how to deploy
- [ ] `README.md` references the `build_docs/` folder for spec
- [ ] `.env.example` is committed and complete
- [ ] If any spec was changed during build, the spec file in `build_docs/` was updated to match

## Operations

- [ ] App boots from a clean state with `docker compose up` (or documented equivalent)
- [ ] Sample data seeded for demo
- [ ] Codex CLI presence detected and surfaced in `/settings` UI
- [ ] Frontend builds without errors and warnings (or warnings are documented and accepted)
- [ ] Backend has no warnings on startup

## UI Polish

- [ ] Classic theme tokens applied uniformly
- [ ] All pages render at ≥ 768px viewport
- [ ] Loading states for every async page section
- [ ] Empty states for every list view (no awkward blank screens)
- [ ] Error states for failed API calls

## Final

- [ ] User can clone the repo, follow README, and have a working agent within 30 minutes
- [ ] User can add a real GitHub repo and watch a no-brainer PR be opened end-to-end without intervention
- [ ] User can pause, resume, stop, retry through the UI

## Artifacts to attach

When declaring done, the following files must be present at the project root:

```
TEST_RESULTS.md
E2E_RESULTS.md
FAILURE_MODE_TESTS.md
COVERAGE.txt
UI_SCREENSHOTS/
README.md
.env.example
```

## Statement of Done

Only when **every** box above is checked and **every** artifact exists, write a final summary message to the user with:
1. The list of what was built
2. The list of any deviations from spec (if any) and why
3. The path to each artifact
4. Any known limitations the user should be aware of

Do not say "done" before this. Do not partially declare done. The whole checklist is the gate.
