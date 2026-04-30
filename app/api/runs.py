from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import PipelineRunCreate, PipelineRunOut
from app.orchestrator.pipeline import PipelineOrchestrator
from app.services.dependencies import get_stop_controller

router = APIRouter()


@router.post("", response_model=PipelineRunOut)
def create_run(
    payload: PipelineRunCreate,
    db: Session = Depends(get_db),
    stop_controller=Depends(get_stop_controller),
) -> PipelineRunOut:
    return PipelineOrchestrator(db, stop_controller).start(payload)


@router.get("/{run_id}", response_model=PipelineRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    stop_controller=Depends(get_stop_controller),
) -> PipelineRunOut:
    return PipelineOrchestrator(db, stop_controller).get(run_id)
