# Validation Policy

After Codex generates a patch, we run validation in the sandbox before opening a PR. Validation = run the repo's own tests/lints/builds and capture results.

## Detection

`sandbox/stack_detector.py` inspects the repo to identify the stack:

| Marker file(s) | Stack |
|---|---|
| `package.json` | Node (JS/TS) |
| `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | Python |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `pom.xml` | Java (Maven) |
| `build.gradle`, `build.gradle.kts` | Java (Gradle) |

A repo can have multiple — pick primary by file count + LOC. Persist to `repository_profile.primary_language`.

## Per-stack commands

Each stack has a default command set. The repo's `repository_profile` may override based on what's actually in the repo's package config / scripts. Detection precedence: **repo override > defaults**.

### Python

| Action | Default attempts (in order) |
|---|---|
| install | `pip install -e .[dev]`, `pip install -r requirements-dev.txt`, `pip install -r requirements.txt`, `poetry install`, `pipenv install --dev` |
| test | `pytest -x`, `python -m pytest -x`, `python -m unittest`, `tox -e py` |
| lint | `ruff check .`, `flake8`, `pylint <pkg>` |
| typecheck | `mypy .`, `pyright` |
| build | `python -m build` |

Override detection: read `pyproject.toml` `[tool.pytest]`, `[tool.ruff]`, etc. Read `tox.ini`. Read `setup.cfg`.

### JavaScript / TypeScript

| Action | Default attempts |
|---|---|
| install | `pnpm install --frozen-lockfile`, `npm ci`, `yarn install --frozen-lockfile`, `bun install` |
| test | `pnpm test`, `npm test`, `yarn test` (use whichever lockfile is present) |
| lint | `pnpm lint`, `npm run lint`, script `eslint .` |
| typecheck | `pnpm typecheck`, `npm run typecheck`, `tsc --noEmit` |
| build | `pnpm build`, `npm run build` |

Override detection: read `package.json` `scripts` keys. Detect package manager via lockfile (`pnpm-lock.yaml` > `yarn.lock` > `package-lock.json` > `bun.lockb`).

### Go

| Action | Default attempts |
|---|---|
| install | `go mod download` |
| test | `go test ./...` |
| lint | `golangci-lint run`, `go vet ./...` |
| build | `go build ./...` |

Override detection: read `Makefile` for `make test` etc.

### Rust

| Action | Default attempts |
|---|---|
| install | `cargo fetch` |
| test | `cargo test --all` |
| lint | `cargo clippy --all-targets -- -D warnings` |
| typecheck | `cargo check --all-targets` |
| build | `cargo build` |

Override detection: read `Cargo.toml` `[workspace]`. Read `.cargo/config.toml`.

### Java (Maven)

| Action | Default attempts |
|---|---|
| install | `mvn -B -DskipTests dependency:resolve` |
| test | `mvn -B test` |
| lint | `mvn -B checkstyle:check`, `mvn -B spotbugs:check` |
| build | `mvn -B package -DskipTests` |

### Java (Gradle)

| Action | Default attempts |
|---|---|
| install | `./gradlew dependencies` |
| test | `./gradlew test` |
| lint | `./gradlew check` |
| build | `./gradlew build -x test` |

## Validation flow

For a given patch:

1. **Install deps** (if not already cached for this clone) — run install command, store cached marker
2. **Run tests** — must pass; capture stdout/stderr/exit code
3. **Run lint** — required if `repository_pr_patterns` shows lint usually passes (>80% of merged PRs)
4. **Run typecheck** — required if stack supports it and project uses it
5. **Run build** — only if quick (skip for large monorepos unless cheap)

Each step's result goes into `validation_results`.

## Pass criteria

A patch is "validated" when:
- `test` exit_code == 0
- `lint` exit_code == 0 (or skipped if lint isn't part of repo's PR culture)
- `typecheck` exit_code == 0 (if applicable)
- `build` exit_code == 0 (if run)

If ANY required step fails:
- Patch marked `validation_failed`
- Capture failing test/lint output
- Pass back to patch generator with the failure context for retry

## Retry with failure context

When retrying patch generation after validation failure:

```
Your previous patch failed validation:

Command: {{FAILING_COMMAND}}
Exit code: {{EXIT_CODE}}
Last 30 lines of output:

{{TAIL}}

Diagnose the failure and produce a corrected patch. Same constraints as before.
```

Retry budget: 2.

## Test command timeout

Per stack:
- Python: 600s
- JS/TS: 600s
- Go: 300s
- Rust: 1800s (slow compiles)
- Java: 900s

If timeout exceeded → mark validation as `timeout`, retry once with `pytest -x --timeout=30` style flags if supported.

## Skipping validation steps

Some repos have flaky lint or massive build steps. Heuristics:

- If `lint` step fails on **unrelated** files (we never touched them) → skip lint, log warning, proceed (linter was already broken on main)
- If `build` takes > 10 min on first install → cache aggressively, skip on subsequent retries
- If repo has no test command detected → mark patch as **NOT validated**, but allow PR with explicit note in body: "no test suite found in repo"

## Test selection optimization

When the repo has thousands of tests, run only the subset relevant to the patch:

- Python: `pytest <test_file_path>` if regression test was added
- JS/TS: `pnpm test -- <test_file>` or `jest <test_file>`
- Go: `go test ./<package>/...`
- Rust: `cargo test <test_name>`

Then run full suite as a final gate before opening PR (faster fail loops, expensive final gate).
