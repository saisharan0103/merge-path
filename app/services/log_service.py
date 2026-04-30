from sqlalchemy.orm import Session

from app.models.db_models import LogEvent


class LogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, message: str, level: str = "INFO", run_id: int | None = None) -> LogEvent:
        event = LogEvent(message=message, level=level, run_id=run_id)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
