# Data Model

## Conventions

- Postgres 15+
- All IDs are `BIGINT` autoincrement (or UUID where noted)
- All timestamps `TIMESTAMPTZ`, default `now()`
- Soft-delete only where needed; mostly hard delete for v1
- Encrypted fields use AES-GCM via `app/utils/crypto.py`

## Tables

### `users`

Single user for v1, but use a table so multi-user is easy later.

```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE,
  password_hash VARCHAR(255),         -- bcrypt
  github_pat_encrypted BYTEA,         -- AES-GCM
  github_username VARCHAR(80),        -- the fork owner identity
  git_commit_email VARCHAR(255),      -- used in commits
  git_commit_name VARCHAR(120),
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### `repositories`

```sql
CREATE TABLE repositories (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,

  upstream_url TEXT NOT NULL,
  upstream_owner VARCHAR(120) NOT NULL,
  upstream_name VARCHAR(120) NOT NULL,
  upstream_default_branch VARCHAR(120) DEFAULT 'main',

  fork_url TEXT NOT NULL,
  fork_owner VARCHAR(120) NOT NULL,
  fork_name VARCHAR(120) NOT NULL,
  fork_verified_at TIMESTAMPTZ,

  language VARCHAR(40),
  stars INT,

  health_score INT,                            -- 0..100
  health_verdict VARCHAR(16),                  -- alive | weak | stale

  current_phase VARCHAR(24),                   -- A_initial | B_buffer | C_continue | cooldown | blacklist
  paused BOOLEAN DEFAULT false,
  pause_reason TEXT,

  next_action_at TIMESTAMPTZ,
  cooldown_until TIMESTAMPTZ,

  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),

  UNIQUE (user_id, upstream_owner, upstream_name)
);

CREATE INDEX ON repositories(user_id);
CREATE INDEX ON repositories(health_verdict);
CREATE INDEX ON repositories(current_phase);
CREATE INDEX ON repositories(next_action_at);
```

### `repository_health_signals`

History of health scans (one row per scan, latest = current).

```sql
CREATE TABLE repository_health_signals (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,

  last_commit_at TIMESTAMPTZ,
  open_pr_count INT,
  merged_pr_count_30d INT,
  median_review_hours NUMERIC(10,2),
  maintainer_response_rate NUMERIC(5,4),       -- 0..1
  release_count_180d INT,
  ci_pass_rate NUMERIC(5,4),
  active_contributors_90d INT,
  external_merge_rate NUMERIC(5,4),

  alive_score INT,
  raw JSONB,                                   -- full signal blob

  fetched_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON repository_health_signals(repo_id, fetched_at DESC);
```

### `repository_profile`

```sql
CREATE TABLE repository_profile (
  repo_id BIGINT PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
  summary TEXT,
  run_commands TEXT[],                         -- e.g., ['npm run dev']
  test_commands TEXT[],
  build_commands TEXT[],
  lint_commands TEXT[],
  install_commands TEXT[],
  prerequisites TEXT[],
  tech_stack VARCHAR(40)[],                    -- ['python', 'fastapi']
  primary_language VARCHAR(40),                -- python | js | ts | go | rust | java | other
  contributing_rules TEXT,                     -- raw CONTRIBUTING.md
  raw_readme TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### `repository_scan` (code map)

```sql
CREATE TABLE repository_scan (
  repo_id BIGINT PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
  file_tree JSONB,
  entrypoints TEXT[],
  test_files TEXT[],
  config_files TEXT[],
  source_dirs TEXT[],
  total_files INT,
  scanned_at TIMESTAMPTZ DEFAULT now()
);
```

### `repository_pr_patterns`

```sql
CREATE TABLE repository_pr_patterns (
  repo_id BIGINT PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
  sample_size INT,
  avg_files_changed NUMERIC(8,2),
  avg_loc_changed NUMERIC(10,2),
  pct_with_tests NUMERIC(5,4),
  pct_with_docs NUMERIC(5,4),
  common_labels TEXT[],
  title_pattern VARCHAR(80),                   -- e.g., 'fix(<scope>): ...'
  median_review_hours NUMERIC(10,2),
  sample_pr_numbers INT[],
  test_required BOOLEAN,                       -- inferred
  docs_required BOOLEAN,
  analyzed_at TIMESTAMPTZ DEFAULT now()
);
```

### `contribution_rules`

Multi-scope rule store.

```sql
CREATE TABLE contribution_rules (
  id BIGSERIAL PRIMARY KEY,
  scope VARCHAR(8) NOT NULL,                   -- global | repo | issue
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  issue_id BIGINT REFERENCES issues(id) ON DELETE CASCADE,
  rule_type VARCHAR(40),                       -- max_files | tests_required | ...
  rule_text TEXT,
  rule_value JSONB,                            -- structured value if applicable
  priority INT DEFAULT 0,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON contribution_rules(scope, repo_id, issue_id, active);
```

### `no_brainer_opportunities`

```sql
CREATE TABLE no_brainer_opportunities (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  type VARCHAR(40),                            -- missing_env_docs | broken_link | ...
  file VARCHAR(500),
  summary TEXT,
  proposed_change TEXT,
  confidence NUMERIC(3,2),                     -- 0.00..1.00
  status VARCHAR(20),                          -- detected | planned | pr_opened | merged | rejected | skipped
  pr_id BIGINT REFERENCES pull_requests(id),
  detected_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON no_brainer_opportunities(repo_id, status);
```

### `issues`

```sql
CREATE TABLE issues (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  github_number INT NOT NULL,
  title TEXT,
  body TEXT,
  labels TEXT[],
  github_state VARCHAR(10),                    -- open | closed
  github_url TEXT,

  score INT,                                   -- 0..100
  eligibility_verdict VARCHAR(20),             -- eligible | filtered | needs_repro | low_score
  filter_reason TEXT,

  reproducibility_confidence NUMERIC(3,2),
  reproduction_log TEXT,

  status VARCHAR(20),                          -- detected | reproducing | reproduced | fixing
                                               -- pr_opened | merged | abandoned | skipped
  abandon_reason TEXT,

  detected_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),

  UNIQUE (repo_id, github_number)
);

CREATE INDEX ON issues(repo_id, status);
CREATE INDEX ON issues(score DESC);
```

### `fix_plans`

Output of Codex plan stage.

```sql
CREATE TABLE fix_plans (
  id BIGSERIAL PRIMARY KEY,
  issue_id BIGINT REFERENCES issues(id) ON DELETE CASCADE,
  run_id BIGINT REFERENCES pipeline_runs(id),
  root_cause TEXT,
  target_files TEXT[],
  target_functions TEXT[],
  approach TEXT,
  tests_to_add TEXT[],
  risk_notes TEXT,
  raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### `patches`

Output of Codex patch stage.

```sql
CREATE TABLE patches (
  id BIGSERIAL PRIMARY KEY,
  issue_id BIGINT REFERENCES issues(id) ON DELETE CASCADE,
  fix_plan_id BIGINT REFERENCES fix_plans(id),
  run_id BIGINT REFERENCES pipeline_runs(id),
  attempt INT,                                 -- 1, 2, 3 (retries)
  diff_text TEXT,
  files_modified TEXT[],
  files_added TEXT[],
  files_deleted TEXT[],
  loc_added INT,
  loc_removed INT,
  codex_stdout TEXT,
  codex_stderr TEXT,
  codex_exit_code INT,
  duration_seconds NUMERIC(8,2),
  status VARCHAR(20),                          -- generated | validated | guardrail_failed | superseded
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### `validation_results`

```sql
CREATE TABLE validation_results (
  id BIGSERIAL PRIMARY KEY,
  patch_id BIGINT REFERENCES patches(id) ON DELETE CASCADE,
  command VARCHAR(40),                         -- test | lint | typecheck | build
  command_text TEXT,
  exit_code INT,
  stdout TEXT,
  stderr TEXT,
  duration_seconds NUMERIC(8,2),
  passed BOOLEAN,
  ran_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON validation_results(patch_id);
```

### `issue_comments`

```sql
CREATE TABLE issue_comments (
  id BIGSERIAL PRIMARY KEY,
  issue_id BIGINT REFERENCES issues(id) ON DELETE CASCADE,
  drafted_text TEXT,
  posted_text TEXT,
  posted_url TEXT,
  github_comment_id BIGINT,
  confidence NUMERIC(3,2),
  status VARCHAR(20),                          -- drafted | posted | skipped
  posted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### `pull_requests`

```sql
CREATE TABLE pull_requests (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  issue_id BIGINT REFERENCES issues(id),
  no_brainer_id BIGINT REFERENCES no_brainer_opportunities(id),
  patch_id BIGINT REFERENCES patches(id),

  type VARCHAR(20),                            -- no_brainer | issue_fix
  upstream_pr_number INT,
  upstream_url TEXT,
  fork_branch_name VARCHAR(200),
  fork_branch_sha VARCHAR(40),
  upstream_base_branch VARCHAR(120),

  title TEXT,
  body TEXT,
  files_changed_count INT,
  loc_added INT,
  loc_removed INT,

  status VARCHAR(20),                          -- open | merged | closed | abandoned
  opened_at TIMESTAMPTZ,
  buffer_until TIMESTAMPTZ,
  grace_until TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  merged_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON pull_requests(repo_id, status);
CREATE INDEX ON pull_requests(buffer_until);
CREATE INDEX ON pull_requests(opened_at DESC);
```

### `pr_traction`

```sql
CREATE TABLE pr_traction (
  id BIGSERIAL PRIMARY KEY,
  pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
  comments_count INT DEFAULT 0,
  maintainer_engaged BOOLEAN DEFAULT false,
  reactions_count INT DEFAULT 0,
  changes_requested BOOLEAN DEFAULT false,
  approved BOOLEAN DEFAULT false,
  traction_score INT DEFAULT 0,
  verdict VARCHAR(12),                         -- pending | positive | negative | neutral
  scored_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON pr_traction(pr_id, scored_at DESC);
```

### `repo_strategy`

```sql
CREATE TABLE repo_strategy (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  current_verdict VARCHAR(12),                 -- green | yellow | red | blacklist
  reason TEXT,
  next_action VARCHAR(40),                     -- ship_no_brainer | escalate_to_issues | wait | drop
  next_action_at TIMESTAMPTZ,
  history JSONB,                               -- list of prior verdicts with timestamps
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX ON repo_strategy(repo_id);
```

### `pipeline_runs`

```sql
CREATE TABLE pipeline_runs (
  id BIGSERIAL PRIMARY KEY,
  repo_id BIGINT REFERENCES repositories(id) ON DELETE CASCADE,
  issue_id BIGINT REFERENCES issues(id),
  no_brainer_id BIGINT REFERENCES no_brainer_opportunities(id),

  kind VARCHAR(20),                            -- onboarding | issue_fix | no_brainer_fix | rescan
  stage VARCHAR(40),                           -- current stage
  status VARCHAR(16),                          -- pending|running|paused|succeeded|failed|abandoned|cancelled

  cancel_requested BOOLEAN DEFAULT false,
  abandon_reason TEXT,
  error TEXT,

  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON pipeline_runs(repo_id, status);
CREATE INDEX ON pipeline_runs(status, created_at DESC);
```

### `log_events`

```sql
CREATE TABLE log_events (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ DEFAULT now(),
  level VARCHAR(8),                            -- info | warn | error
  stage VARCHAR(40),
  message TEXT,
  meta JSONB
);

CREATE INDEX ON log_events(run_id, ts);
```

### `settings_kv`

Generic key-value for app settings.

```sql
CREATE TABLE settings_kv (
  key VARCHAR(80) PRIMARY KEY,
  value JSONB,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

Examples: `buffer_multiplier`, `max_concurrent_runs`, `min_health_score`, `pause_all`.

## ER Summary

```
users 1—* repositories
repositories 1—1 repository_profile
repositories 1—1 repository_scan
repositories 1—1 repository_pr_patterns
repositories 1—1 repo_strategy
repositories 1—* repository_health_signals
repositories 1—* no_brainer_opportunities
repositories 1—* issues
repositories 1—* pipeline_runs
repositories 1—* pull_requests

issues 1—* fix_plans
issues 1—* patches
issues 1—* issue_comments
issues 1—* pull_requests

fix_plans 1—* patches
patches 1—* validation_results
patches 1—1 pull_requests

pull_requests 1—* pr_traction

pipeline_runs 1—* log_events
```

## Migrations

Use Alembic. Generate one migration per phase in build order:
- `0001_users_repositories`
- `0002_health_profile_scan`
- `0003_pr_patterns_no_brainers`
- `0004_issues_plans_patches_validation`
- `0005_pull_requests_traction_strategy`
- `0006_pipeline_runs_logs_settings`
