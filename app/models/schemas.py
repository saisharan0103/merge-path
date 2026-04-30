from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepositoryConfigBase(BaseModel):
    allowed_labels: list[str] = Field(default_factory=list)
    allowed_issue_types: list[str] = Field(default_factory=list)
    max_files_changed: int = 10
    require_tests_pass: bool = True
    require_lint_pass: bool = True
    require_build_pass: bool = False
    auto_pr_enabled: bool = False
    auto_comment_enabled: bool = False


class RepositoryConfigCreate(RepositoryConfigBase):
    pass


class RepositoryConfigUpdate(BaseModel):
    allowed_labels: list[str] | None = None
    allowed_issue_types: list[str] | None = None
    max_files_changed: int | None = None
    require_tests_pass: bool | None = None
    require_lint_pass: bool | None = None
    require_build_pass: bool | None = None
    auto_pr_enabled: bool | None = None
    auto_comment_enabled: bool | None = None


class RepositoryConfigOut(RepositoryConfigBase):
    id: int
    repository_id: int

    model_config = ConfigDict(from_attributes=True)


class RepositoryCreate(BaseModel):
    repo_url: HttpUrl
    owner: str | None = None
    name: str | None = None
    default_branch: str = "main"
    local_path: str | None = None
    is_enabled: bool = True
    config: RepositoryConfigCreate = Field(default_factory=RepositoryConfigCreate)


class RepositoryUpdate(BaseModel):
    owner: str | None = None
    name: str | None = None
    default_branch: str | None = None
    local_path: str | None = None
    is_enabled: bool | None = None
    config: RepositoryConfigUpdate | None = None


class RepositoryOut(BaseModel):
    id: int
    owner: str
    name: str
    repo_url: str
    default_branch: str
    local_path: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    config: RepositoryConfigOut | None = None

    model_config = ConfigDict(from_attributes=True)


class IssueFilter(BaseModel):
    owner: str
    repo: str
    labels: list[str] = Field(default_factory=list)
    max_items: int = 20


class RepositoryIssueOut(BaseModel):
    id: int
    repository_id: int
    number: int
    title: str
    html_url: str
    state: str
    labels: list[str]
    is_assigned: bool
    is_pull_request: bool
    is_eligible: bool
    rejection_reasons: list[str]
    github_created_at: str | None = None
    github_updated_at: str | None = None
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueFetchResult(BaseModel):
    fetched: int
    stored: int
    skipped_existing: int
    total_stored: int
    eligible_stored: int


class RepositoryScanOut(BaseModel):
    id: int
    repository_id: int
    local_path: str
    is_cloned: bool
    tech_stack: list[str]
    package_manager: str | None
    has_test_config: bool
    has_lint_config: bool
    has_build_config: bool
    contribution_docs: list[str]
    important_files: list[str]
    last_scanned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineRunCreate(BaseModel):
    repository_id: int | None = None
    issue_number: int | None = None
    dry_run: bool = True


class PipelineRunOut(BaseModel):
    id: int
    repository_id: int | None = None
    issue_number: int | None = None
    status: str
    current_step: str
    branch_name: str | None = None
    pull_request_url: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
