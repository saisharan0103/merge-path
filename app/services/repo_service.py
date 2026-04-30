from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.github.issues import IssueClient
from app.models.db_models import Repository, RepositoryConfig, RepositoryIssue
from app.models.schemas import (
    IssueFetchResult,
    IssueFilter,
    RepositoryCreate,
    RepositoryIssueOut,
    RepositoryOut,
    RepositoryUpdate,
)
from app.repo.manager import RepoManager
from app.utils.repo_url import derive_owner_name, normalize_repo_url

ALLOWED_ISSUE_LABELS = {"good first issue", "help wanted", "bug", "documentation"}


class RepoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.issues = IssueClient()
        self.manager = RepoManager()

    def create(self, payload: RepositoryCreate) -> RepositoryOut:
        repo_url = normalize_repo_url(str(payload.repo_url))
        owner, name = self._owner_name(payload.owner, payload.name, repo_url)
        self._ensure_unique_repo_url(repo_url)

        repository = Repository(
            owner=owner,
            name=name,
            repo_url=repo_url,
            default_branch=payload.default_branch,
            local_path=payload.local_path,
            is_enabled=payload.is_enabled,
            config=RepositoryConfig(**payload.config.model_dump()),
        )
        self.db.add(repository)
        self.db.commit()
        self.db.refresh(repository)
        return RepositoryOut.model_validate(repository)

    def onboard(self, payload: RepositoryCreate) -> RepositoryOut:
        repo_url = normalize_repo_url(str(payload.repo_url))
        local_path = str(self.manager.clone_or_update(repo_url))
        payload_data = payload.model_dump()
        payload_data["repo_url"] = repo_url
        payload_data["local_path"] = local_path
        return self.create(RepositoryCreate(**payload_data))

    def list(self) -> list[RepositoryOut]:
        stmt = (
            select(Repository)
            .options(selectinload(Repository.config))
            .order_by(desc(Repository.created_at))
        )
        return [RepositoryOut.model_validate(repo) for repo in self.db.scalars(stmt).all()]

    def get(self, repository_id: int) -> RepositoryOut:
        return RepositoryOut.model_validate(self._get_model(repository_id))

    def update(self, repository_id: int, payload: RepositoryUpdate) -> RepositoryOut:
        repository = self._get_model(repository_id)
        data = payload.model_dump(exclude_unset=True)
        config_data = data.pop("config", None)
        if "repo_url" in data:
            data["repo_url"] = normalize_repo_url(data["repo_url"])
        for key, value in data.items():
            setattr(repository, key, value)
        if config_data and repository.config:
            for key, value in config_data.items():
                setattr(repository.config, key, value)
        self.db.commit()
        self.db.refresh(repository)
        return RepositoryOut.model_validate(repository)

    def set_enabled(self, repository_id: int, enabled: bool) -> RepositoryOut:
        repository = self._get_model(repository_id)
        repository.is_enabled = enabled
        self.db.commit()
        self.db.refresh(repository)
        return RepositoryOut.model_validate(repository)

    def fetch_candidate_issues(self, payload: IssueFilter) -> list[dict[str, object]]:
        return self.issues.list_repo_issues(owner=payload.owner, repo=payload.repo, max_items=payload.max_items)

    def fetch_repository_issues(self, repository_id: int, max_items: int = 100) -> IssueFetchResult:
        repository = self._get_model(repository_id)
        raw_issues = self.issues.list_repo_issues(repository.owner, repository.name, max_items=max_items)
        existing_numbers = set(
            self.db.scalars(select(RepositoryIssue.number).where(RepositoryIssue.repository_id == repository.id))
        )

        stored = 0
        skipped_existing = 0
        for raw_issue in raw_issues:
            number = int(raw_issue["number"])
            if number in existing_numbers:
                skipped_existing += 1
                continue
            issue = self._build_issue(repository.id, raw_issue)
            self.db.add(issue)
            existing_numbers.add(number)
            stored += 1

        self.db.commit()
        return self._issue_fetch_result(
            repository_id=repository.id,
            fetched=len(raw_issues),
            stored=stored,
            skipped_existing=skipped_existing,
        )

    def list_repository_issues(self, repository_id: int, eligible_only: bool = False) -> list[RepositoryIssueOut]:
        self._get_model(repository_id)
        stmt = (
            select(RepositoryIssue)
            .where(RepositoryIssue.repository_id == repository_id)
            .order_by(RepositoryIssue.is_eligible.desc(), RepositoryIssue.number.asc())
        )
        if eligible_only:
            stmt = stmt.where(RepositoryIssue.is_eligible.is_(True))
        return [RepositoryIssueOut.model_validate(issue) for issue in self.db.scalars(stmt).all()]

    def _build_issue(self, repository_id: int, raw_issue: dict[str, object]) -> RepositoryIssue:
        labels = [
            str(label.get("name", "")).strip()
            for label in raw_issue.get("labels", [])
            if isinstance(label, dict) and label.get("name")
        ]
        rejection_reasons = self._rejection_reasons(raw_issue, labels)
        return RepositoryIssue(
            repository_id=repository_id,
            number=int(raw_issue["number"]),
            title=str(raw_issue.get("title") or ""),
            html_url=str(raw_issue.get("html_url") or ""),
            state=str(raw_issue.get("state") or ""),
            labels=labels,
            is_assigned=bool(raw_issue.get("assignee") or raw_issue.get("assignees")),
            is_pull_request="pull_request" in raw_issue,
            is_eligible=not rejection_reasons,
            rejection_reasons=rejection_reasons,
            github_created_at=raw_issue.get("created_at"),
            github_updated_at=raw_issue.get("updated_at"),
        )

    def _rejection_reasons(self, raw_issue: dict[str, object], labels: list[str]) -> list[str]:
        reasons: list[str] = []
        if raw_issue.get("state") != "open":
            reasons.append("closed")
        if "pull_request" in raw_issue:
            reasons.append("pull_request")
        if raw_issue.get("assignee") or raw_issue.get("assignees"):
            reasons.append("assigned")
        if not {label.lower() for label in labels}.intersection(ALLOWED_ISSUE_LABELS):
            reasons.append("missing_allowed_label")
        return reasons

    def _issue_fetch_result(
        self,
        repository_id: int,
        fetched: int,
        stored: int,
        skipped_existing: int,
    ) -> IssueFetchResult:
        total_stored = int(
            self.db.scalar(select(func.count()).select_from(RepositoryIssue).where(RepositoryIssue.repository_id == repository_id))
            or 0
        )
        eligible_stored = int(
            self.db.scalar(
                select(func.count())
                .select_from(RepositoryIssue)
                .where(RepositoryIssue.repository_id == repository_id, RepositoryIssue.is_eligible.is_(True))
            )
            or 0
        )
        return IssueFetchResult(
            fetched=fetched,
            stored=stored,
            skipped_existing=skipped_existing,
            total_stored=total_stored,
            eligible_stored=eligible_stored,
        )

    def _get_model(self, repository_id: int) -> Repository:
        stmt = (
            select(Repository)
            .options(selectinload(Repository.config))
            .where(Repository.id == repository_id)
        )
        repository = self.db.scalar(stmt)
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        return repository

    def _ensure_unique_repo_url(self, repo_url: str) -> None:
        existing = self.db.scalar(select(Repository).where(Repository.repo_url == repo_url))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Repository with this repo_url already exists")

    @staticmethod
    def _owner_name(owner: str | None, name: str | None, repo_url: str) -> tuple[str, str]:
        derived_owner, derived_name = derive_owner_name(repo_url)
        owner = owner or derived_owner
        name = name or derived_name
        if not owner:
            raise HTTPException(status_code=422, detail="owner is required or must be derivable from repo_url")
        if not name:
            raise HTTPException(status_code=422, detail="name is required or must be derivable from repo_url")
        return owner, name
