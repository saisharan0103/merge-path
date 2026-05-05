# Fork + PR Strategy

## Model

Each `Repository` row has **two URLs**:

- `upstream_url` — official repo (e.g., `https://github.com/facebook/react`)
- `fork_url` — user's personal fork (e.g., `https://github.com/myname/react`)

Internal canonicalization:

```python
@dataclass
class RepoIdentity:
    upstream_owner: str       # facebook
    upstream_name: str        # react
    upstream_default_branch: str  # main
    fork_owner: str           # myname
    fork_name: str            # react
    fork_default_branch: str  # main (usually same)
```

## Verification on Add

When user submits both URLs in the Add Repo modal:

```
POST /repos
{
  "upstream_url": "...",
  "fork_url": "..."
}
```

Backend MUST verify (in this order, fail fast on each):

1. Both URLs are valid GitHub URLs (regex + host check)
2. Both repos exist via GitHub API (`GET /repos/{owner}/{repo}`)
3. Fork repo's `parent.full_name` matches upstream's `full_name`. If not — **reject**:
   ```json
   {"error": "fork_not_of_upstream", "message": "..."}
   ```
4. User's PAT has push access to the fork (try `GET /repos/{fork}/collaborators/{me}/permission`, or simpler — verify fork ownership matches PAT's authenticated user)
5. Upstream is not archived/disabled

If any step fails, the repo is NOT created. Surface the specific error in UI.

## Git Operations

All git ops happen in the cloned working directory:

```
$WORKDIR/repos/<repo_id>/<run_id>/
```

### Initial clone

Clone the **fork** (not upstream). Add upstream as a remote:

```bash
git clone <fork_url> .
git remote add upstream <upstream_url>
git fetch upstream
```

### Sync fork before each issue

Before creating any new branch, ensure the fork's default branch is up-to-date with upstream:

```bash
git checkout <default_branch>
git fetch upstream
git reset --hard upstream/<default_branch>
git push origin <default_branch> --force-with-lease
```

`--force-with-lease` is safer than `--force`. Skip this if the fork has its own commits we want preserved (rare; default behavior is to keep fork in sync).

### Branch per issue/no-brainer

Branch naming:

| Type | Pattern | Example |
|---|---|---|
| Issue fix | `patchpilot/issue-{n}-{slug}` | `patchpilot/issue-4231-fix-empty-input-error` |
| No-brainer | `patchpilot/docs-{type}-{ts}` | `patchpilot/docs-setup-20260501-1430` |

`{slug}` = first 6 words of issue title, lowercased, alphanum + dashes only, max 40 chars.

### Commit

```bash
git add <only files in scope>
git -c user.email="$GIT_EMAIL" -c user.name="$GIT_NAME" commit -m "<message>"
```

Commit message format (see `policies/branch_pr_conventions.md`):
```
fix(<area>): <one-line description>

Closes #<issue_number>
```

### Push

```bash
git push origin <branch_name> -u
```

If branch already exists (e.g., from previous attempt that didn't open PR), use `--force-with-lease`.

### Open PR (fork → upstream)

Via GitHub API:
```python
github.get_repo(upstream).create_pull(
    title=pr_title,
    body=pr_body,
    head=f"{fork_owner}:{branch_name}",   # cross-fork PR head ref
    base=upstream_default_branch,
    maintainer_can_modify=True,
)
```

Always pass `maintainer_can_modify=True`. Maintainers expect this on OSS contributions.

## Idempotency

- Branch already exists? → push with `--force-with-lease`
- PR for this branch already exists? → skip creation, attach existing PR record. Do NOT open a duplicate.
- Issue already has a PR from us? → skip the entire fix pipeline; mark issue as `pr_already_exists`.

## Cleanup

After PR is opened, the working directory is kept for 24h for debugging, then deleted. If user clicks "View Logs" the diff and logs are still readable from DB.

If a PR is closed without merge:
- Branch on fork is **kept** for 30 days (in case user wants to inspect)
- After 30 days, agent deletes the fork branch via API

## Multiple PRs to same repo

Each issue gets its own branch and PR. We never bundle. We do limit to **N concurrent open PRs per upstream** (default 3) to avoid spamming a maintainer.

## Edge cases

| Case | Handling |
|---|---|
| Fork is behind by hundreds of commits | Sync as above; if conflicts on sync, abandon, log, alert UI |
| Upstream renamed | Detect via API redirect, update `upstream_url` automatically, log |
| Fork deleted by user | All ops fail → mark repo as `red`, surface error |
| User revokes PAT | All ops fail → mark all repos paused, surface in settings |
| Upstream merges our PR but our fork branch still exists | Auto-delete branch from fork after detecting merge |
| User contributes manually outside agent | Agent ignores those; only tracks PRs it opened |

## What's stored

`pull_requests` table fields specific to this strategy:

```
upstream_pr_number     int
fork_branch_name       str
fork_branch_sha        str
upstream_base_branch   str
maintainer_can_modify  bool
```

`repositories` table:

```
upstream_url            str
upstream_owner          str
upstream_name           str
upstream_default_branch str
fork_url                str
fork_owner              str
fork_name               str
fork_verified_at        timestamp
```
