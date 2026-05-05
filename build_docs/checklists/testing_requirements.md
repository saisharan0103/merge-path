# Testing Requirements

The build is not considered complete until **all** of the following are produced and pass.

## 1. Unit Tests (per module)

Every service module must have unit tests with mocked external dependencies.

| Module | Tests must cover |
|---|---|
| `health_scorer` | Each signal contributes correctly; verdict thresholds; missing data handling |
| `profiler` | Parses READMEs of all 5 stacks; extracts run/test commands; handles missing CONTRIBUTING |
| `code_mapper` | Builds tree, identifies entrypoints/tests/configs for each stack |
| `pr_pattern_analyzer` | Computes averages; derives `test_required`; handles small samples |
| `no_brainer_scanner` | Each detection type triggers correctly; false positives bounded |
| `issue_scorer` | Each signal scored; hard filters work; score breakdown returned |
| `repro_engine` | Confidence computation; timeout handling; stack trace parsing |
| `codex_runner` | Subprocess invocation; timeout; scope violation detection; empty diff |
| `guardrails` | All rejection rules trigger; pass case allows |
| `comment_planner` | Skip conditions respected; word count enforced; banned phrases rejected |
| `pr_writer` | Template enforcement; deterministic fallback works |
| `traction_scorer` | Each signal awards/deducts correct points |
| `strategy_adapter` | Verdict transitions per traction thresholds |
| `github_client` | Retry on 5xx; rate-limit waiting; auth failure handling |

Coverage target: **≥ 80% line coverage** on `services/`.

## 2. Integration Tests

Run against a test Postgres + mocked GitHub responses (use `responses` library or VCR).

- Add repo → verifies row, enqueues run, run completes
- Onboarding pipeline end-to-end with fixtures
- Issue fix pipeline end-to-end with fixtures (uses a fake CodexRunner that returns canned diff)
- Traction polling with simulated PR state changes
- Strategy adapter with simulated traction history

## 3. API Endpoint Tests (`TEST_RESULTS.md`)

For **every** endpoint in `api/API_CONTRACT.md`, produce:

```markdown
### POST /repos

**Request:**
```json
{ ... }
```

**Response (201):**
```json
{ ... }
```

**Other status codes covered:**
- 400 fork_not_of_upstream (sample req/res)
- 409 repo_already_exists (sample req/res)
- 422 validation (sample req/res)

**Auth verified:** ✅ (401 without token)

**Curl example:**
```bash
curl -X POST http://localhost:8000/api/v1/repos \
  -H "Authorization: Bearer $JWT" \
  -d '{...}'
```
```

`TEST_RESULTS.md` must cover every endpoint listed in §8 of the API contract. No exceptions.

## 4. E2E Tests Against Real Repos (`E2E_RESULTS.md`)

Run the actual agent against **5 real public repos**, one per stack. For each:

```markdown
### Python: pallets/click

- Onboarding run ID: 42
- Health score: 92, verdict: alive
- Profile detected: ✅ (run/test commands listed)
- PR patterns: ✅ (sample size 40, test_required=true)
- No-brainers detected: 3
- No-brainer PR opened: https://github.com/pallets/click/pull/<n>
- Branch on fork: patchpilot/no-brainer-env-vars-...
- Validation: tests passed locally
- PR description: passed validation
- SSE log stream: 142 events captured
```

Repeat for JS/TS, Go, Rust, Java.

Also include:
- 1 stale repo test (verdict should be `stale`, pipeline halts)
- 1 fork-not-of-upstream rejection (manual API call, expect 400)

## 5. Frontend Tests

- Each page loads without console errors
- Each chart renders with the live API data
- Each filter/sort/paginate control updates the visible rows
- Add Repo modal validates both URLs before submitting
- Pause/Resume buttons reflect state immediately
- Run detail page receives SSE events live

Capture screenshots: `UI_SCREENSHOTS/<page>.png` for each page in `prd/PRD.md` §9.

## 6. Performance / Smoke

Not full perf testing, but smoke checks:

- Onboarding pipeline completes for a healthy repo in < 5 minutes
- Issue fix pipeline (with mock Codex returning canned diff) completes in < 2 minutes
- Dashboard `GET /metrics/overview` < 500ms with 1000 PRs in DB
- 5 concurrent SSE clients on same run: all receive events within 2s

## 7. Failure Mode Verification

Manually trigger or simulate each failure in `policies/failure_modes.md` and verify the documented action. Document in `FAILURE_MODE_TESTS.md`:

```markdown
### GitHub 401 (PAT revoked)

Test: Set PAT to garbage in DB, trigger any GitHub call.
Expected: All repos paused, alert in `/settings`, run failed with `pat_invalid`.
Result: ✅
```

Cover at least 15 most important failure modes.

## 8. Run setup verification

A fresh clone of the project, following the README, must:

- Bring up Postgres, Redis, FastAPI, Celery, frontend with one command (e.g., `docker compose up` or `make dev`)
- Run migrations cleanly
- Seed sample data (one alive repo, one stale, one with PRs)
- Show populated dashboard within 30s

This is verified by reading the README from clean terminal and following it line by line. If any step fails, fix README, re-test.

## Mandatory artifacts

All of the following files/folders must exist and be filled in before declaring done:

```
TEST_RESULTS.md              # all endpoints
E2E_RESULTS.md               # 5 real repos + edge cases
FAILURE_MODE_TESTS.md        # 15+ failure modes
UI_SCREENSHOTS/              # one per page
COVERAGE.txt                 # output of pytest --cov, ≥80%
```

If any are missing or contain unfilled placeholders → not done.
