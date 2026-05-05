# Prompt: Fix Planner

**Stage:** `plan_fix`
**Tool:** Codex CLI (subprocess, non-interactive)
**Output target:** `./fix_plan.json` written to repo working dir
**Input scope:** read-only (no file edits allowed in this stage)

## How it's used

The orchestrator writes this prompt (with placeholders filled) to a temp file and invokes:

```
codex exec --cwd <repo_clone_dir> --prompt-file <prompt.md> --non-interactive
```

After Codex finishes, the orchestrator reads `fix_plan.json` and parses it into the `fix_plans` table.

## Prompt template

````md
You are a senior open-source contributor. Your job in this step is to PLAN a fix
for a specific GitHub issue. You will NOT write any code yet. You will only
produce a structured plan.

## Repository
- Upstream: {{UPSTREAM_OWNER}}/{{UPSTREAM_NAME}}
- Primary language: {{PRIMARY_LANGUAGE}}
- Tech stack: {{TECH_STACK}}

## Issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}

{{ISSUE_BODY}}

## Reproduction (already verified by the agent)

The issue has been reproduced on the latest default branch.

Reproduction steps used:
{{REPRO_STEPS}}

Captured output (relevant excerpt):
```
{{REPRO_LOG_EXCERPT}}
```

Stack trace pointing to:
- File: {{STACK_FILE}}
- Function: {{STACK_FUNCTION}}
- Line: {{STACK_LINE}}

## Code map (relevant slices only)

Source directories: {{SOURCE_DIRS}}
Test directories: {{TEST_DIRS}}

Likely involved files (you may inspect these):
{{CANDIDATE_FILES}}

## Repository contribution rules (must respect)

- Smallest possible diff. Maximum {{MAX_FILES}} files. Maximum {{MAX_LOC}} lines changed.
- One PR = one problem. Do NOT plan changes outside the issue's scope.
- Do NOT plan formatting-only changes, dependency upgrades, or refactors.
- Tests {{TESTS_STANCE}}: {{TESTS_NOTE}}
- Repo PR title pattern: `{{TITLE_PATTERN}}`

## Your task

Read the candidate files. Identify the precise root cause. Produce a fix plan
strictly in the JSON schema below. Write it to the file `./fix_plan.json`
in the repo root. Do NOT modify any source file in this step.

## Output schema (write to ./fix_plan.json)

```json
{
  "root_cause": "<one paragraph: what is actually wrong>",
  "target_files": ["<path/to/file1>", "<path/to/file2>"],
  "target_functions": ["<func name in file1>", "..."],
  "approach": "<2-4 sentences describing the minimal change>",
  "tests_to_add": ["<test name or description>"],
  "expected_loc": <integer: estimated lines added+removed>,
  "risk_notes": "<short: anything that could go wrong>",
  "out_of_scope_observations": "<short: things you noticed but will NOT fix>"
}
```

Constraints on your plan:
- `target_files` must be ≤ {{MAX_FILES}} entries
- `expected_loc` must be ≤ {{MAX_LOC}}
- If you cannot find a root cause from the provided context, write
  `{"root_cause": null, "abort_reason": "<why>"}` — and nothing else — to fix_plan.json

End your turn after writing fix_plan.json. Do not explain the plan in chat output;
the JSON file IS the output.
````

## Placeholder reference

| Placeholder | Source |
|---|---|
| `{{UPSTREAM_OWNER}}/{{UPSTREAM_NAME}}` | `repositories` row |
| `{{PRIMARY_LANGUAGE}}` | `repository_profile.primary_language` |
| `{{TECH_STACK}}` | comma-joined `repository_profile.tech_stack` |
| `{{ISSUE_NUMBER/TITLE/BODY}}` | `issues` row |
| `{{REPRO_STEPS}}` | reproduction engine output |
| `{{REPRO_LOG_EXCERPT}}` | last 30 lines of reproduction stderr/stdout |
| `{{STACK_FILE/FUNCTION/LINE}}` | parsed from stack trace |
| `{{SOURCE_DIRS}}` | `repository_scan.source_dirs` |
| `{{TEST_DIRS}}` | derived from `repository_scan.test_files` |
| `{{CANDIDATE_FILES}}` | top 10 files matching stack + heuristics |
| `{{MAX_FILES}}` | `min(repo_pattern.avg_files * 1.5, 5)` |
| `{{MAX_LOC}}` | `min(repo_pattern.avg_loc * 1.5, 200)` |
| `{{TESTS_STANCE}}` | `"required"` if `pr_patterns.test_required` else `"encouraged"` |
| `{{TESTS_NOTE}}` | "If a test is reasonable, add one" |
| `{{TITLE_PATTERN}}` | `pr_patterns.title_pattern` |

## Validation after Codex returns

Orchestrator parses `fix_plan.json`:
- If file missing → `error=plan_missing`, retry once
- If `abort_reason` set → mark issue `abandoned` with that reason
- If `target_files` exceeds budget → `error=plan_over_budget`, retry once with stricter budget
- If valid → persist to `fix_plans` table, proceed to patch stage

## Anti-patterns to detect

After parse, run these heuristic checks. If any trigger, retry once with a stricter prompt:
- `target_files` includes lockfiles (`package-lock.json`, `poetry.lock`, `Cargo.lock`, `go.sum`) — reject
- `target_files` includes CI configs, README, license — reject (those are for no-brainer pipeline)
- `approach` mentions "refactor", "rewrite", "redesign" — flag as scope risk
- `expected_loc` > `MAX_LOC` — reject
