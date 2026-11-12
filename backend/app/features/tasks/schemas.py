from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskSubmissionCreate(BaseModel):
    remarks: str = Field(..., min_length=1, description="Remarks and summary of work done for submission")
    file_url: Optional[str] = Field(None, max_length=500, description="Optional pre-existing deliverable URL")
    file_name: Optional[str] = Field(None, max_length=255, description="Deliverable original filename")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="Deliverable file size in bytes")

    model_config = ConfigDict(from_attributes=True)


class TaskResubmitSchema(BaseModel):
    revised_remarks: str = Field(..., description="Remarks describing fixes and updates made following rejection")
    new_file_url: Optional[str] = Field(None, description="URL pointing to the revised deliverable or evidence archive")

    @model_validator(mode="before")
    @classmethod
    def allow_aliases(cls, data: object) -> object:
        if isinstance(data, dict):
            # Support remarks / revised_remarks
            if "revised_remarks" not in data and "remarks" in data:
                data["revised_remarks"] = data["remarks"]
            # Support file_url / new_file_url
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
