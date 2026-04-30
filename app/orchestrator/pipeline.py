from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.db_models import PipelineRun
from app.models.schemas import PipelineRunCreate, PipelineRunOut
from app.orchestrator.stop_controller import StopController


class PipelineOrchestrator:
    """Minimal recovery orchestrator: records queued runs only."""

    def __init__(self, db: Session, stop_controller: StopController) -> None:
        self.db = db
        self.stop_controller = stop_controller

    def start(self, payload: PipelineRunCreate) -> PipelineRunOut:
        if self.stop_controller.stop_requested:
            raise HTTPException(status_code=409, detail="Pipeline is stopped")
        run = PipelineRun(
            repository_id=payload.repository_id,
            issue_number=payload.issue_number,
            status="queued",
            current_step="created",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return PipelineRunOut.model_validate(run)

    def get(self, run_id: int) -> PipelineRunOut:
        run = self.db.get(PipelineRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return PipelineRunOut.model_validate(run)
