from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
