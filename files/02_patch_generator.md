# Prompt: Patch Generator

**Stage:** `generate_patch`
**Tool:** Codex CLI (subprocess, non-interactive, file-write enabled)
**Output target:** edits to source files + new/updated test file(s)
**Input scope:** files listed in `fix_plan.target_files` + test files

## How it's used

Orchestrator builds prompt by injecting the fix plan from the previous stage. Invokes:

```
codex exec \
  --cwd <repo_clone_dir> \
  --prompt-file <prompt.md> \
  --non-interactive \
  --max-loc <MAX_LOC> \
  --scope <file1> --scope <file2> ...
```

Diff is captured by the wrapper via `git diff` after Codex returns.

## Prompt template

````md
You are a senior open-source contributor. Your task is to implement a fix
according to the plan below. Make the SMALLEST possible change.

## Repository
- Upstream: {{UPSTREAM_OWNER}}/{{UPSTREAM_NAME}}
- Primary language: {{PRIMARY_LANGUAGE}}
- Test runner: {{TEST_COMMAND}}
- Lint runner: {{LINT_COMMAND}}

## Issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}

{{ISSUE_BODY_SHORT}}

## Approved Fix Plan

Root cause: {{PLAN_ROOT_CAUSE}}

Target files (you may ONLY modify these and the test files listed below):
{{PLAN_TARGET_FILES}}

Test files you may add or modify:
{{TEST_FILES}}

Approach: {{PLAN_APPROACH}}

Tests to add: {{PLAN_TESTS_TO_ADD}}

Risk notes: {{PLAN_RISK_NOTES}}

Out-of-scope observations (DO NOT FIX THESE — they are noted for later):
{{PLAN_OUT_OF_SCOPE}}

## Hard constraints

1. Modify ONLY the files listed above. Touching any other file is a violation.
2. Maximum {{MAX_LOC}} lines added+removed total.
3. Add the regression test(s) listed in "Tests to add" if reasonable.
4. Do NOT add new dependencies. If you think one is needed, abort instead.
5. Do NOT change formatting on lines you don't need to touch.
6. Do NOT rename anything, do NOT refactor unrelated code.
7. Match the repo's existing style in the file you're editing.
8. The fix must make the reproduction case pass and must not break existing tests.

## Workflow

1. Read each target file.
2. Read the existing tests in the test files.
3. Implement the minimal change.
4. Add the regression test(s).
5. Run the test command in your head — verify your test would actually catch
   the bug it's protecting against.
6. Save all files. End your turn.

## Abort signal

If you discover the fix requires:
- a new dependency,
- changes to files outside the allowlist,
- more than {{MAX_LOC}} lines, or
- a redesign

then write a single file `./abort.txt` containing the reason and STOP. Do not
make any source-file edits in that case.

End your turn after the change is saved (or after writing abort.txt).
````

## Placeholder reference

| Placeholder | Source |
|---|---|
| `{{TEST_COMMAND}}` | `repository_profile.test_commands[0]` |
| `{{LINT_COMMAND}}` | `repository_profile.lint_commands[0]` |
| `{{ISSUE_BODY_SHORT}}` | first 1500 chars of issue body |
| `{{PLAN_*}}` | from `fix_plans` row |
| `{{TEST_FILES}}` | tests near target files (heuristic) |
| `{{MAX_LOC}}` | from runtime budget (`fix_plan.expected_loc * 1.2`, capped at 200) |

## After Codex returns

Wrapper:
1. Check `abort.txt` exists → mark patch failed, abandon issue with that reason
2. Run `git diff` → capture diff text
3. Parse files modified/added/deleted
4. Validate scope: any file outside allowlist? → `scope_violation`, retry with explicit re-listing
5. Validate LOC budget: exceeded? → `over_budget`, retry with stricter budget
6. Empty diff? → `empty_diff`, retry with prompt clarification
7. Pass → save to `patches` table, proceed to validation stage

## Retry strategy

Retry budget: 2.

| First failure | Retry prompt addition |
|---|---|
| empty_diff | "Your previous attempt produced no changes. The bug definitely exists at <stack_file>:<line>. Please make the change explicitly." |
| scope_violation | "Your previous attempt modified files outside the allowlist: <files>. Touch ONLY: <allowlist>. Move any unrelated insight to abort.txt." |
| over_budget | "Your previous attempt was too large (<actual> LOC). Reduce to <stricter_budget> LOC. Cut anything not strictly required." |
| codex_timeout | "Focus only on the minimum change. Skip any analysis or commentary. Just edit and save." |

After 2 failures → patch stage marked failed, issue marked abandoned with `abandon_reason=patch_generation_failed`.
