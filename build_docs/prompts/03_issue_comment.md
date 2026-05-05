# Prompt: Issue Comment Generator

**Stage:** `post_comment`
**Tool:** Anthropic / Codex CLI (text generation only — no file ops)
**Output:** comment markdown written to `./comment.md`

## When this runs

After the patch is validated AND guardrails pass AND fork branch is pushed.
Before opening the PR.

The comment is posted to the upstream issue as a precursor to the PR. This is
how senior contributors signal "I have the fix in hand" without burning
maintainer attention.

## Skip conditions (orchestrator-level, before invoking the prompt)

The orchestrator skips the comment entirely (does NOT invoke this prompt) if:
- `reproducibility_confidence < 0.7`
- Issue already has an open assignee
- Issue already has another open PR linked
- Repo's contribution rules say "do not comment on issues" (read from CONTRIBUTING)

## Prompt template

````md
You are a senior open-source contributor leaving a brief, factual comment on a
GitHub issue. The comment must sound like a real human contributor, not a bot.

## Style rules

- Maximum 5 lines of body text (excluding code blocks/lists).
- No "Hi!", no "Thanks for filing!", no apology, no fluff.
- Do NOT say "Can I work on this?" or any variant.
- Do NOT promise timelines.
- Use plain markdown.
- Reference exact file:function paths where possible.
- Past tense for what you did, future tense for the PR.

## Context

Issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}

Reproduction (verified):
{{REPRO_STEPS_BRIEF}}

Captured behavior:
- Expected: {{EXPECTED}}
- Actual: {{ACTUAL}}

Root cause (from fix plan): {{PLAN_ROOT_CAUSE}}
Source location: {{PLAN_TARGET_FILES_FIRST}}:{{TARGET_FUNCTION}}

Patch already pushed to branch: {{FORK_BRANCH}}
PR will be opened next.

## Comment shape (write to ./comment.md)

Structure must be:

```
I reproduced this on latest {{DEFAULT_BRANCH}} (<commit-sha-short>).

**Repro:** <one line>
**Expected:** <one line>
**Actual:** <one line>

Root cause looks like `<file>:<function>` — <one short sentence on why>.

Opening a focused PR with a regression test shortly.
```

Replace placeholders with the actual content. Keep it tight.

If reproduction was via a code snippet from the issue body, say:
"Reproduced using the snippet from the issue body."
instead of inventing steps.

End your turn after writing comment.md.
````

## Placeholder reference

| Placeholder | Source |
|---|---|
| `{{ISSUE_NUMBER/TITLE}}` | `issues` row |
| `{{REPRO_STEPS_BRIEF}}` | reproduction engine, first 3 lines |
| `{{EXPECTED/ACTUAL}}` | parsed from reproduction or issue body |
| `{{PLAN_ROOT_CAUSE}}` | `fix_plans.root_cause` (first sentence) |
| `{{PLAN_TARGET_FILES_FIRST}}` | first entry of `fix_plans.target_files` |
| `{{TARGET_FUNCTION}}` | first entry of `fix_plans.target_functions` |
| `{{FORK_BRANCH}}` | `pull_requests.fork_branch_name` |
| `{{DEFAULT_BRANCH}}` | `repositories.upstream_default_branch` |

## Post-generation validation

Orchestrator reads `comment.md` and rejects (regenerate once) if:
- Word count > 100
- Contains "Can I" or "may I" or "Hi " or "Thanks "
- Contains "TODO" or "TBD" placeholders
- Missing the file:function reference
- More than 2 question marks (sounds uncertain)

If validation passes, post via GitHub:

```python
github.get_repo(upstream).get_issue(issue_number).create_comment(comment_body)
```

Persist to `issue_comments` with `status='posted'` and `posted_url`.

## Failure mode

If generation fails twice → skip the comment entirely and proceed to PR.
A clean PR with a clean description is better than a forced/weak comment.
Mark `issue_comments.status='skipped'` with reason.
