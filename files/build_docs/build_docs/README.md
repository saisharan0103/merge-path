# Build Docs — Autonomous OSS Contribution Agent

This folder contains everything Claude Code needs to build the agent. Hand it the whole folder.

## Structure

```
build_docs/
├── README.md                          ← you are here (index + build order)
├── .env.example                       ← required env vars
├── prd/
│   └── PRD.md                         ← product spec (what + why)
├── specs/
│   ├── 01_architecture.md             ← system overview, modules, data flow
│   ├── 02_pipeline_state_machine.md   ← run lifecycle, sync vs async, retries
│   ├── 03_codex_integration.md        ← subprocess wrapper design
│   ├── 04_fork_pr_strategy.md         ← upstream + fork URL flow
│   └── 05_log_streaming.md            ← SSE + polling hybrid
├── api/
│   └── API_CONTRACT.md                ← every endpoint, request/response shapes
├── data/
│   └── DATA_MODEL.md                  ← all tables, FKs, indexes
├── prompts/
│   ├── 01_fix_planner.md              ← Codex prompt for fix plan
│   ├── 02_patch_generator.md          ← Codex prompt for patch
│   ├── 03_issue_comment.md            ← maintainer-style comment
│   └── 04_pr_description.md           ← PR body
├── policies/
│   ├── validation_policy.md           ← per-stack test/lint/build commands
│   ├── branch_pr_conventions.md       ← naming, commit format, templates
│   └── failure_modes.md               ← error catalog + handling
└── checklists/
    ├── acceptance_criteria.md         ← per-feature pass/fail
    ├── testing_requirements.md        ← what must be tested
    └── done_checklist.md              ← final handoff checklist
```

## Reading order for Claude Code

1. **prd/PRD.md** — understand the product
2. **specs/01_architecture.md** — understand the system shape
3. **data/DATA_MODEL.md** — set up DB
4. **api/API_CONTRACT.md** — set up endpoints
5. **specs/02_pipeline_state_machine.md** — implement run engine
6. **specs/03_codex_integration.md** — wire Codex
7. **specs/04_fork_pr_strategy.md** — wire GitHub flow
8. **prompts/** — drop into Codex calls
9. **policies/** — apply during validation/PR creation
10. **checklists/** — verify before handoff

## Build order (phases)

| Phase | Focus | Specs to follow |
|---|---|---|
| 1 | DB + skeleton + auth | data, api (auth + repos) |
| 2 | Health scorer + profile + code map | specs/01, api/repos |
| 3 | PR pattern analyzer + no-brainer scanner | specs/01 |
| 4 | Issue scorer + reproduction engine + Codex | specs/02, 03, prompts |
| 5 | Comment + PR creation (fork flow) | specs/04, prompts, policies |
| 6 | Traction scorer + strategy adapter | specs/01 |
| 7 | Frontend (all pages) + log streaming | specs/05, PRD §9 |
| 8 | Testing + checklists | checklists/ |

## Tech stack (locked)

- **Backend:** Python + FastAPI
- **DB:** PostgreSQL
- **Queue:** Celery + Redis
- **GitHub:** PyGithub + raw REST for things PyGithub doesn't cover
- **Codex:** subprocess wrapper around Codex CLI
- **Frontend:** Next.js + React + TypeScript + Tailwind
- **Charts:** Recharts
- **Auth:** Single-user JWT (PAT stored encrypted)
- **Sandbox:** Python `subprocess` with timeout in dev; Docker later

## Hard rule for handoff

Build is NOT done until `checklists/done_checklist.md` is fully checked and the test artifacts referenced inside it exist and pass.
