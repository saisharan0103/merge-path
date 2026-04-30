from app.core.config import settings
from app.db.session import Base, engine
from app.models import db_models


def init_db() -> None:
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.clone_dir.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        from pathlib import Path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
