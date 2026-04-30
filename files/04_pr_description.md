# Prompt: PR Description Generator

**Stage:** `open_pr`
**Tool:** Anthropic / Codex CLI (text generation only)
**Output:** PR title + body written to `./pr.json`

## Format

The PR body uses a HARD template. The model fills sections; structure is fixed.

## Prompt template

````md
You are writing a GitHub pull request title and body for an open-source contribution.
The body MUST follow the exact template structure below. No deviations.

## Context

Issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}

Repo PR title pattern observed: `{{TITLE_PATTERN}}`
(If no pattern exists, default to: `fix: <short description>`)

Root cause: {{PLAN_ROOT_CAUSE}}
Approach taken: {{PLAN_APPROACH}}

Files changed: {{FILES_CHANGED}}
Lines added: {{LOC_ADDED}}
Lines removed: {{LOC_REMOVED}}

Tests run by validation:
{{VALIDATION_COMMANDS_AND_RESULTS}}

Regression test added: {{REGRESSION_TEST_FILE}}

## Style rules

- Title ≤ 70 characters. Lowercase except acronyms. Match repo title pattern.
- Body sections in this exact order: ## What changed, ## Why, ## How tested, Fixes #N
- Total body word count ≤ 250
- No emoji, no marketing language, no "I" / "me" — write impersonally
- No "thanks", no "please review", no apologies
- Code references in backticks
- Bullets only inside ## How tested if needed

## Output schema (write to ./pr.json)

```json
{
  "title": "<title following repo pattern>",
  "body": "<full body following template>"
}
```

## Body template (fill exactly)

```markdown
## What changed

<2–3 sentences: specific change made, in plain terms. Reference file/function.>

## Why

<2–4 sentences: the root cause and why this fix addresses it. Reference issue.>

## How tested

- Existing tests: <pass/fail summary>
- New regression test: `<path/to/test_file>::<test_name>` — covers <what>
- Validation commands: `<cmd1>`, `<cmd2>`

Fixes #{{ISSUE_NUMBER}}
```

End your turn after writing pr.json.
````

## Placeholder reference

| Placeholder | Source |
|---|---|
| `{{TITLE_PATTERN}}` | `repository_pr_patterns.title_pattern` |
| `{{PLAN_*}}` | `fix_plans` row |
| `{{FILES_CHANGED}}` | `patches.files_modified + files_added` |
| `{{LOC_ADDED/REMOVED}}` | `patches.loc_added`, `patches.loc_removed` |
| `{{VALIDATION_COMMANDS_AND_RESULTS}}` | latest `validation_results` rows |
| `{{REGRESSION_TEST_FILE}}` | first new test file in `patches.files_added` |

## Post-generation validation

Orchestrator parses `pr.json` and rejects (regenerate once) if any of:
- `title` length > 70 chars
- Body word count > 250
- Body missing `## What changed`, `## Why`, or `## How tested` headings
- Body missing `Fixes #{{ISSUE_NUMBER}}` line
- Body contains "thanks", "please", "I will", "I have", "in this PR I"
- Title contains hype words: "amazing", "improved", "better", "comprehensive"

If validation fails twice → fall back to a deterministic template that fills
fields directly from DB without LLM:

```python
title = f"fix: address #{{ISSUE_NUMBER}} - {{ISSUE_TITLE_TRUNCATED}}"
body = f"""## What changed

{{PLAN_APPROACH}}

## Why

{{PLAN_ROOT_CAUSE}}

## How tested

- Existing tests: passed
- Regression test added: `{{REGRESSION_TEST_FILE}}`
- Validation: `{{TEST_COMMAND}}`

Fixes #{{ISSUE_NUMBER}}
"""
```

The deterministic fallback is ugly but correct. Better than a malformed PR.

## After validation passes

Open PR via API:

```python
pr = github.get_repo(upstream_full_name).create_pull(
    title=title,
    body=body,
    head=f"{fork_owner}:{fork_branch_name}",
    base=upstream_default_branch,
    maintainer_can_modify=True,
)
```

Persist to `pull_requests` table with `upstream_pr_number`, `upstream_url`,
`opened_at = now()`, compute `buffer_until` and `grace_until` from repo's
median review time. Schedule traction check Celery beat job.
