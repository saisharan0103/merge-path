# Mergepath

PatchPilot is a local-first FastAPI backend for experimenting with an autonomous GitHub contribution pipeline.

This repository is currently in recovery mode. The backend is intentionally minimal and runnable; advanced automation is stubbed for later steps.

## What Works

- FastAPI application startup
- SQLite database initialization
- Health endpoint
- Repository metadata CRUD
- Minimal repository onboarding UI
- Basic repo onboarding that clones a repository into `workspace/repos`
- GitHub issue fetch and V1 eligibility filtering
- Queued pipeline run records
- Metrics summary
- Stop/clear control switch

## What Is Stubbed

- Repository scanning
- Codex execution
- Validation command execution
- Fork, push, and pull request creation

## Setup

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

The root page is a small development UI for adding repositories, listing them, and toggling enabled/disabled status.
Set `GITHUB_TOKEN` in `.env` before using the issue fetch button. The V1 issue policy stores fetched issues, skips already stored issues, and marks issues eligible only when they are open, unassigned, not pull requests, and have at least one allowed label.

## Useful Endpoints

```text
GET  /api/v1/health
GET  /api/v1/metrics
GET  /api/v1/repos
GET  /api/v1/repos/{repository_id}
POST /api/v1/repos
POST /api/v1/repos/onboard
POST /api/v1/repos/{repository_id}/enable
POST /api/v1/repos/{repository_id}/disable
POST /api/v1/repos/{repository_id}/issues/fetch
GET  /api/v1/repos/{repository_id}/issues
GET  /api/v1/repos/{repository_id}/issues/eligible
POST /api/v1/runs
```
