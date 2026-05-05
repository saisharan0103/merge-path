# PRD: Autonomous OSS Contribution Agent

**Status:** v1 — Build Spec
**Last updated:** May 2026

---

## 1. Problem

Picking and contributing to OSS repos manually is slow. Most contributors get ignored because they ship low-quality PRs, comment "can I work on this?", or pick dead repos.

We're building a **fully autonomous agent** that behaves like a senior contributor: scores repos, learns merge culture, picks small reproducible issues, ships clean PRs, adapts based on traction.

**Zero human input after starting a repo.**

---

## 2. Goals

- Autonomously contribute to OSS repos with real merge probability
- Build trust in 5–8 repos in parallel
- Skip what we can't reproduce — never engage without proof
- Track every PR's traction and adapt strategy per repo
- Full UI to monitor, override, and analyze

## 3. Non-Goals (v1)

- UI/visual bug fixes (CSS, layout, mobile, browser-specific)
- Issues needing paid services or external accounts
- Big refactors, security fixes, payment/auth changes
- Semantic code retrieval and PR memory — deferred
- Multi-tenant — single-user app

---

## 4. Core Principles (hard rules)

1. One PR = one problem
2. Smallest possible diff
3. Reproduce before code, comment with proof
4. Skip silently when confidence < 0.7
5. Spread across repos, never spam one
6. Tests added when relevant
7. Maintainer-friendly PR template enforced
8. No formatting noise, no opportunistic cleanup

---

## 5. User Flow (high level)

1. User adds a repo by entering **two URLs**: upstream (main repo) and fork (user's fork)
2. Agent scores health → if green, scans repo, learns merge culture
3. Agent detects no-brainer opportunities → opens 1–2 docs PRs from fork
4. Agent waits buffer (`median_review × 2`, min 7d, max 21d) + 5d grace
5. Agent scores traction → green/yellow/red/blacklist
6. On green repos, agent picks reproducible issues, generates fix in fork branch, opens PR to upstream
7. User views everything in dashboard

---

## 6. System Layers

```
[Repo: upstream URL + fork URL]
    ↓
[Layer A: Health Scorer]            → alive / weak / stale → skip if dead
    ↓
[Layer 1: Profile (READMEs, etc)]
    ↓
[Layer 2: Code Map]
    ↓
[Layer B: PR Pattern Analyzer]      → last 20–40 merged PRs of upstream
    ↓
[Layer 0: No-Brainer Scanner]       → docs/setup friction
    ↓
[Issue Picker + Scorer]             → upstream issues only
    ↓
[Reproduction Engine]               → sandbox + Codex CLI + terminal
    ↓
[Confidence Gate ≥ 0.7]             → else skip silently
    ↓
[Codex Fix Generator]               → branch on fork, commit, push
    ↓
[PR Guardrails]
    ↓
[Issue Comment (upstream) + PR (fork → upstream)]
    ↓
[Buffer Wait + Traction Scorer]
    ↓
[Strategy Adapter]                  → continue / pause / cooldown / drop
```

---

## 7. Multi-Language Support (v1)

Validation, sandbox setup, and patch generation must work for:

- **Python** (pip, poetry, pipenv)
- **JavaScript / TypeScript** (npm, pnpm, yarn)
- **Go** (go modules)
- **Rust** (cargo)
- **Java** (maven, gradle)

Detector inspects `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle` to identify stack. See `policies/validation_policy.md`.

---

## 8. Key Concepts

### 8.1 Repo with Upstream + Fork

A `Repository` row stores **both** URLs:
- `upstream_url` — the project's official repo (where issues live, where PRs are sent to)
- `fork_url` — the user's personal fork (where branches and commits are pushed)

Agent reads issues and PRs from upstream, pushes branches to fork, opens PRs from `fork:branch` → `upstream:default_branch`.

### 8.2 Branch per issue

Every issue gets its own branch:
```
patchpilot/issue-{number}-{slug}
patchpilot/no-brainer-{type}-{timestamp}
```

### 8.3 Reproduction confidence gate

Reproduction confidence < 0.7 → skip silently, never comment, never PR.

### 8.4 Traction-driven strategy

Per-repo verdict updates after every PR's buffer expires:
- 🟢 GREEN — continue, escalate
- 🟡 YELLOW — 1–2 more no-brainers, watch
- 🔴 RED — cooldown 30 days, recheck once
- ⛔ BLACKLIST — permanent

---

## 9. Frontend Pages (Classic Theme)

### Theme tokens
- Background: `#FAF8F3` (cream)
- Text: `#1A1A1A` (deep ink)
- Borders: `#D4CFC0`
- Accents: forest green `#2D5016`, oxblood `#7C2D12`, navy `#1E3A8A`
- Headings: `Source Serif Pro` / `Lora`
- Body: `Inter` / `IBM Plex Sans`
- Mono: `JetBrains Mono`
- Borders ≤ 4px radius
- Dense tables, no card bloat

### Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — stats, time-series, recent activity, verdict distribution, funnel |
| `/repos` | Repo table — sortable, filterable |
| `/repos/:id` | Repo detail — tabs: Overview, Health, Code Map, PR Patterns, No-Brainers, Issues, PRs, Strategy, Logs |
| `/scores` | Repo scores leaderboard |
| `/issues` | All issues across repos, filterable |
| `/issues/:id` | Issue detail — body, score breakdown, repro logs, comment, PR link |
| `/prs` | All PRs, "By Repo" or "All" view |
| `/prs/:id` | PR detail — body, diff stats, traction timeline, buffer countdown |
| `/strategy` | Per-repo strategy table, cooldown queue, blacklist |
| `/activity` | Live agent activity log |
| `/settings` | PAT, fork credentials, sandbox toggle, buffer multiplier, pause-all |

### Add Repo modal

Two inputs:
1. **Upstream Repo URL** — `github.com/owner/repo`
2. **Your Fork URL** — `github.com/your-username/repo`

Agent verifies fork is actually a fork of upstream via GitHub API.

---

## 10. Acceptance Criteria (high level)

See `checklists/acceptance_criteria.md` for full list.

Top-level:
1. Add repo → health + verdict shown within 60s
2. Profile + code map + PR patterns within 5 minutes
3. No-brainer opportunities listed
4. Agent autonomously opens 1 no-brainer PR per green repo
5. Buffer + traction tracking visible
6. Strategy verdict updates automatically
7. Dashboard shows accurate daily/weekly/monthly counts
8. Pause toggle works per repo
9. All 11 pages functional
10. Classic theme applied consistently

---

## 11. Out of Scope (v2 backlog)

- Multi-user / teams
- Public deployment
- Notifications (email, Slack)
- Visual bug reproduction
- Auto-following maintainer feedback on open PRs
- Repo recommendation engine

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| GitHub rate limit | Authenticated PAT (5000/hr), aggressive caching, exponential backoff |
| Codex generates bad code | Guardrails + 2 retries + abandon-and-log |
| Flagged as spam | Spread repos, conservative buffers, never re-PR closed PR |
| Sandbox security | Subprocess with timeout in dev, Docker prod |
| PAT compromise | Encrypted at rest, env var only |
| Fork out of sync | Auto-rebase from upstream before each branch |

---

## 13. Definition of Done

See `checklists/done_checklist.md`. Build is done **only** when that checklist is fully satisfied with attached test artifacts.
