from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.db_models import LogEvent, PipelineRun, Repository


class MetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self) -> dict[str, int]:
        return {
            "repos": self._count(Repository),
            "runs": self._count(PipelineRun),
            "logs": self._count(LogEvent),
        }

    def _count(self, model: object) -> int:
        return int(self.db.scalar(select(func.count()).select_from(model)) or 0)
