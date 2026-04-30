from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("")
def get_metrics(db: Session = Depends(get_db)) -> dict[str, int]:
    return MetricsService(db).summary()
