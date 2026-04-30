from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    repo_url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    config: Mapped["RepositoryConfig"] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        uselist=False,
    )
    runs: Mapped[list["PipelineRun"]] = relationship(back_populates="repository")


class RepositoryConfig(Base):
    __tablename__ = "repository_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), unique=True)
    allowed_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_issue_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_files_changed: Mapped[int] = mapped_column(Integer, default=10)
    require_tests_pass: Mapped[bool] = mapped_column(Boolean, default=True)
    require_lint_pass: Mapped[bool] = mapped_column(Boolean, default=True)
    require_build_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_pr_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_comment_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    repository: Mapped[Repository] = relationship(back_populates="config")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int | None] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(100), default="queued")
    current_step: Mapped[str] = mapped_column(String(255), default="created")
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    repository: Mapped[Repository | None] = relationship(back_populates="runs")
    logs: Mapped[list["LogEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(50), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[PipelineRun | None] = relationship(back_populates="logs")


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
