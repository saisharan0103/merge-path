# Branch + PR Conventions

## Branch Naming

```
patchpilot/issue-{number}-{slug}
patchpilot/no-brainer-{type}-{ts}
```

- `{slug}` = first 6 words of issue title, lowercase, alphanumeric + dash, max 40 chars
- `{type}` for no-brainers: `setup-docs`, `env-vars`, `troubleshooting`, `broken-links`, `windows-notes`, etc.
- `{ts}` = `YYYYMMDD-HHMM` UTC

Examples:
```
patchpilot/issue-4231-fix-empty-input-error
patchpilot/issue-89-handle-trailing-slash-in-url
patchpilot/no-brainer-setup-docs-20260501-1430
patchpilot/no-brainer-env-vars-20260502-0915
```

## Commit Message

Single commit per PR (squash if Codex created multiple). Format:

```
{type}({scope}): {description}

{body — optional, only if useful context not in PR body}

Closes #{issue_number}
```

`{type}`: `fix`, `docs`, `test`, `chore` (only for no-brainers)
`{scope}`: derived from primary file path (e.g., `parser`, `cli`, `auth`); fall back to omitting `({scope})` if unclear.

Examples:
```
fix(parser): handle empty input without crashing

Closes #4231
```

```
docs(setup): document required environment variables

Closes #1234
```

If repo's PR pattern analyzer shows a different convention (e.g. "no scope", "ALLCAPS prefix"), the agent matches the repo's pattern.

## Commit Author

```
git -c user.email="$GIT_COMMIT_EMAIL" -c user.name="$GIT_COMMIT_NAME" commit -m "..."
```

`GIT_COMMIT_EMAIL` and `GIT_COMMIT_NAME` come from `users` table.

## PR Title

Match repo pattern detected by `PRPatternAnalyzer`. Common patterns:

| Repo style | Example title |
|---|---|
| `fix(<scope>): <desc>` | `fix(parser): handle empty input` |
| `[<area>] <desc>` | `[parser] Handle empty input` |
| `<desc> (#issue)` | `Handle empty input (#4231)` |
| Plain | `Handle empty input in parser` |

Title rules (regardless of style):
- Max 70 chars
- Lowercase except acronyms and proper nouns
- No trailing period
- No emoji
- Reference the issue number ONLY if the repo's pattern includes it (some do, some don't)

## PR Body Template

Hard template — see `prompts/04_pr_description.md`:

```markdown
## What changed

<2–3 sentences>

## Why

<2–4 sentences>

## How tested

- Existing tests: <pass/fail summary>
- New regression test: `<path>::<test_name>` — covers <what>
- Validation commands: `<cmd1>`, `<cmd2>`

Fixes #<issue_number>
```

For no-brainer PRs:

```markdown
## What changed

<list of doc additions>

## Why

<one sentence — friction observed during fresh setup>

## How tested

- Followed updated README from a fresh clone
- Verified all documented commands run
```

## PR Settings

- `maintainer_can_modify: true` (always)
- `draft: false` (we only open when ready)
- Labels: do NOT add labels — that's the maintainer's job
- Reviewers: do NOT request specific reviewers — disrespectful from external contributor
- Milestones: never assign
- Linked issue: GitHub auto-links via `Fixes #N`; do NOT also add to "Linked issues" sidebar (no API for it as external anyway)

## Cross-Fork PR head reference

```
head: "{fork_owner}:{branch_name}"
base: "{upstream_default_branch}"
```

## When PR Already Exists

Before opening, check:
```python
existing = list(repo.get_pulls(
    state='open',
    head=f"{fork_owner}:{branch_name}",
))
```

If found → update title and body via `pr.edit(title=..., body=...)`, do NOT open new. Persist as same `pull_requests` row.

## Editing After Open (limited)

After PR is open, the agent may:
- Push additional commits if maintainer requests changes (handled by future feedback-loop feature; out of v1 scope)
- Close the PR if the issue was closed by someone else with a better fix
- Update PR body once if a typo or missing reference is detected

The agent MUST NOT:
- Reopen a closed PR
- Delete the branch while PR is open
- Comment on its own PR pushing for review (annoying)

## After Merge

When PR is merged (detected via traction polling):
- Mark `pull_requests.status='merged'`, set `merged_at`
- Auto-delete fork branch (via API) after 7 days
- Trigger `StrategyAdapter` to update repo verdict

## After Close (no merge)

- Mark `pull_requests.status='closed'`
- Read close reason if maintainer commented
- Keep fork branch for 30 days (then auto-delete)
- Update traction with `−5` per traction policy
