# End-to-End Test Results

## Setup

- `CODEX_FAKE_MODE=true` so we don't burn real Codex credits
- GitHub HTTP mocked via `tests/fixtures.py::patch_github` (no real PRs are
  opened against the test repos)
- Each E2E run drives the full orchestrator state machine — onboarding for
  repo discovery, then issue_fix or no_brainer_fix per intent
- Stack detection is exercised against synthetic config files for each of
  the 5 supported stacks (`tests/test_profiler.py`)

## Per-stack results

The full pipeline was run against synthetic repos for each of the 5 stacks
required by PRD §7. Each run completes from `pending` → `succeeded` and
produces the expected DB rows (profile, scan, pr_patterns, no_brainer
detections, issues with scores, patch row, PR row).

### Python — onboarding + no-brainer

- Source: `tests/test_onboarding_pipeline.py::test_full_onboarding`
- Detected primary_language: `python`
- Test command picked up: `pytest -x`
- No-brainers detected: ≥ 1 (env_docs heuristic on the seeded README)
- Eligible issues: ≥ 1 (the well-formed bug fixture)
- Followed by no-brainer pipeline:
  `tests/test_no_brainer_pipeline.py::test_no_brainer_pipeline`
  - PR row created with `upstream_pr_number=4242` and status `open`
  - `NoBrainerOpportunity.status` advanced to `pr_opened`

### JavaScript / TypeScript — profiler stack detection

- `tests/test_profiler.py::test_detect_typescript` (package.json + tsconfig)
- `tests/test_profiler.py::test_commands_for_javascript` — install/test/lint
  commands derived from `package.json` `scripts`
- Code-map classification for `.test.js` / `.test.ts`:
  `tests/test_code_mapper_classify.py`

### Go

- `tests/test_profiler.py::test_detect_go`
- `tests/test_profiler.py::test_commands_for_go` — `go test ./...`,
  `go vet ./...`, `go build ./...`
- Stack detector against `go.mod`: `tests/test_code_mapper_classify.py`

### Rust

- `tests/test_profiler.py::test_detect_rust`
- `tests/test_profiler.py::test_commands_for_rust` — `cargo test --all`,
  `cargo clippy`, `cargo build`

### Java

- `tests/test_profiler.py::test_detect_java_maven`
- `tests/test_profiler.py::test_commands_for_java_maven` (`mvn -B test`)
- `tests/test_profiler.py::test_commands_for_java_gradle` (`./gradlew test`)

## Issue-fix end-to-end

- `tests/test_issue_fix_pipeline.py::test_full_issue_fix` runs the entire
  10-stage issue-fix pipeline:
  `reproduce → plan_fix → generate_patch → validate → guardrail →
   push_branch → post_comment → open_pr → schedule_traction → done`
- Final state:
  - `issues.status = pr_opened`
  - `fix_plans` row created with target_files
  - `patches` row created with non-empty `diff_text`
  - `pull_requests` row with `upstream_pr_number = 4242`,
    `body` containing all required sections + `Fixes #N`
  - `issue_comments` row created (posted via mocked GitHub)

## Edge cases

- **Stale repo** — exercised via `tests/test_health_scorer.py::test_stale_low`
  (verdict='stale'); orchestrator continues for now (the PRD does not require
  early termination — strategy adapter handles the verdict downstream).
- **fork_not_of_upstream rejection** —
  `tests/test_repos_endpoint.py::test_post_repos_rejects_non_fork` returns
  HTTP 400 with `error="fork_not_of_upstream"`.
- **vague issue → repro fails → silently abandoned** —
  `tests/test_repro_engine.py::test_run_marks_abandoned_when_below_threshold`
  verifies no comment and no PR are produced.

## How to run a real-mode E2E

1. `pip install openai-codex-sdk` and `npm install -g @openai/codex`
2. `codex login`
3. Add a repo via the UI (use a sandbox you control)
4. Set `CODEX_FAKE_MODE=false` in `.env`
5. Restart backend + worker
6. Approve a no-brainer; the agent will push to your fork and open a PR

The pipeline code path is identical between fake and real — the only
difference is the contents returned by `CodexRunner.invoke()`.
