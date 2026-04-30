from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import IssueFilter, RepositoryCreate, RepositoryOut, RepositoryUpdate
from app.services.repo_service import RepoService

router = APIRouter()


@router.post("", response_model=RepositoryOut)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepoService(db).create(payload)


@router.post("/onboard", response_model=RepositoryOut)
def onboard_repo(payload: RepositoryCreate, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepoService(db).onboard(payload)


@router.get("", response_model=list[RepositoryOut])
def list_repositories(db: Session = Depends(get_db)) -> list[RepositoryOut]:
    return RepoService(db).list()


@router.get("/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: int, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepoService(db).get(repository_id)


@router.patch("/{repository_id}", response_model=RepositoryOut)
def update_repository(
    repository_id: int,
    payload: RepositoryUpdate,
    db: Session = Depends(get_db),
) -> RepositoryOut:
    return RepoService(db).update(repository_id, payload)


@router.post("/{repository_id}/enable", response_model=RepositoryOut)
def enable_repository(repository_id: int, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepoService(db).set_enabled(repository_id, True)


@router.post("/{repository_id}/disable", response_model=RepositoryOut)
def disable_repository(repository_id: int, db: Session = Depends(get_db)) -> RepositoryOut:
    return RepoService(db).set_enabled(repository_id, False)


@router.post("/issues")
def fetch_issues(payload: IssueFilter, db: Session = Depends(get_db)) -> dict[str, object]:
    return {"items": RepoService(db).fetch_candidate_issues(payload)}
