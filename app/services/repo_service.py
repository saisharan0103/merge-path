from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.github.issues import IssueClient
from app.models.db_models import Repository, RepositoryConfig
from app.models.schemas import IssueFilter, RepositoryCreate, RepositoryOut, RepositoryUpdate
from app.repo.manager import RepoManager
from app.utils.repo_url import derive_owner_name, normalize_repo_url


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
        return self.issues.list_candidate_issues(
            owner=payload.owner,
            repo=payload.repo,
            labels=payload.labels,
            max_items=payload.max_items,
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
