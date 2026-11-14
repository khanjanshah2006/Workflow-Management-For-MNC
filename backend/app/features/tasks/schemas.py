from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.enums import PriorityLevel, TaskStatus


# ============================================================================
# US-11: Task Submission Schemas
# ============================================================================

class TaskSubmissionCreate(BaseModel):
    remarks: str = Field(..., min_length=1, description="Remarks and summary of work done for submission")
    file_url: Optional[str] = Field(None, max_length=500, description="Optional pre-existing deliverable URL")
    file_name: Optional[str] = Field(None, max_length=255, description="Deliverable original filename")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="Deliverable file size in bytes")

    model_config = ConfigDict(from_attributes=True)


class TaskSubmissionResponse(BaseModel):
    submission_id: int = Field(..., description="Unique submission identifier")
    task_id: int = Field(..., description="Associated task identifier")
    submitted_by: Optional[int] = Field(None, description="Employee ID of the submitter")
    remarks: str = Field(..., description="Employee submission remarks")
    file_url: Optional[str] = Field(None, description="Accessible URL or path to uploaded deliverable file")
    file_name: Optional[str] = Field(None, description="Original filename of attached deliverable")
    file_size_bytes: Optional[int] = Field(None, description="Size of uploaded deliverable in bytes")
    submitted_at: datetime = Field(..., description="Timestamp when the deliverable was submitted")

    model_config = ConfigDict(from_attributes=True)


class TaskSubmissionsListResponse(BaseModel):
    task_id: int
    task_title: str
    task_status: str
    submissions: List[TaskSubmissionResponse] = []
    total_submissions: int = 0

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# US-13: Task Review Queue & Resubmit Schemas
# ============================================================================

class TaskResubmitSchema(BaseModel):
    revised_remarks: str = Field(..., description="Remarks describing fixes and updates made following rejection")
    new_file_url: Optional[str] = Field(None, description="URL pointing to the revised deliverable or evidence archive")

    @model_validator(mode="before")
    @classmethod
    def allow_aliases(cls, data: object) -> object:
        if isinstance(data, dict):
            if "revised_remarks" not in data and "remarks" in data:
                data["revised_remarks"] = data["remarks"]
            if "new_file_url" not in data and "file_url" in data:
                data["new_file_url"] = data["file_url"]
        return data

    model_config = ConfigDict(from_attributes=True)


class TaskReviewQueueItem(BaseModel):
    task_id: int
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    team_id: Optional[int] = None
    project_id: Optional[int] = None
    milestone_id: Optional[int] = None
    assigned_to: Optional[int] = None
    assignee_name: Optional[str] = None
    submission_remarks: Optional[str] = None
    deliverable_file_url: Optional[str] = None
    submission_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None
    due_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class TaskResubmitResponse(BaseModel):
    task_id: int
    title: str
    status: str
    team_id: Optional[int] = None
    assigned_to: Optional[int] = None
    submission_id: Optional[int] = None
    revised_remarks: Optional[str] = None
    new_file_url: Optional[str] = None
    message: str = "Task resubmitted successfully"

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# US-33: Task Comments Schemas
# ============================================================================

class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment content must not be blank.")
        return value


class TaskCommentResponse(BaseModel):
    comment_id: int
    task_id: int
    author_emp_id: Optional[int] = None
    author_name: str
    author_role: str
    content: str
    created_at: datetime
    edited_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# US-10: Task Progress & Blocker Tracking Schemas
# ============================================================================

class TaskProgressStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"


class TaskProgressUpdateSchema(BaseModel):
    status: TaskProgressStatus = Field(
        ...,
        description="Target task progress status (IN_PROGRESS or BLOCKED)",
    )
    progress_pct: int = Field(
        ...,
        ge=0,
        le=100,
        description="Task completion percentage between 0 and 99 (100% requires submitting via review flow)",
    )
    blocker_reason: Optional[str] = Field(
        None,
        description="Explanation of the blocker when status is BLOCKED (minimum 5 characters)",
    )

    @model_validator(mode="after")
    def validate_blocker_reason(self) -> "TaskProgressUpdateSchema":
        if self.status == TaskProgressStatus.BLOCKED:
            if not self.blocker_reason or len(self.blocker_reason.strip()) < 5:
                raise ValueError("blocker_reason is required and must be at least 5 characters when status is BLOCKED")
        return self

    model_config = ConfigDict(from_attributes=True)


class TaskProgressResponse(BaseModel):
    task_id: int = Field(..., description="Unique task identifier")
    project_id: int = Field(..., description="Associated project identifier")
    team_id: Optional[int] = Field(None, description="Associated team identifier")
    assigned_to: Optional[int] = Field(None, description="Assigned employee identifier")
    title: str = Field(..., description="Task title")
    status: str = Field(..., description="Current status of the task")
    progress_pct: int = Field(0, description="Current progress percentage (0-100)")
    blocker_reason: Optional[str] = Field(None, description="Current blocker explanation if blocked")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the task was completed")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# S3: Task Lifecycle Schemas (US-09, US-32)
# ============================================================================

class TaskCreate(BaseModel):
    project_id: int = Field(..., ge=1)
    team_id: int = Field(..., ge=1)
    milestone_id: Optional[int] = Field(None, ge=1)
    assigned_to: Optional[int] = Field(None, ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: PriorityLevel = PriorityLevel.MEDIUM
    start_date: Optional[date] = None
    due_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title must not be blank.")
        return cleaned


class ProjectSummary(BaseModel):
    project_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MilestoneSummary(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeSummary(BaseModel):
    emp_id: int
    full_name: str
    email: str
    designation: str

    model_config = ConfigDict(from_attributes=True)


class TaskDetailResponse(BaseModel):
    task_id: int
    project_id: int
    team_id: int
    milestone_id: Optional[int] = None
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: PriorityLevel
    status: TaskStatus
    progress_pct: int
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    rejection_count: int
    rejection_feedback: Optional[str] = None
    blocker_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectSummary] = None
    milestone: Optional[MilestoneSummary] = None
    assignee: Optional[EmployeeSummary] = None
    creator: Optional[EmployeeSummary] = None

    model_config = ConfigDict(from_attributes=True)


class TaskSummaryResponse(BaseModel):
    task_id: int
    project_id: int
    team_id: int
    milestone_id: Optional[int] = None
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    title: str
    priority: PriorityLevel
    status: TaskStatus
    progress_pct: int
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTasksResponse(BaseModel):
    items: List[TaskSummaryResponse] = []
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)
