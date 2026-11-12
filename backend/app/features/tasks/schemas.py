from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PriorityLevel, TaskStatus


# ==========================================
# Task Assignment & Reassignment Schemas (US-09, US-14)
# ==========================================

class TaskAssignRequest(BaseModel):
    """Payload to assign an unassigned task or set assignee (US-09)."""
    assignee_id: int = Field(..., gt=0, description="Target employee ID to assign the task to")


class TaskReassignRequest(BaseModel):
    """Payload to reassign an active task to another team member (US-14)."""
    new_assignee_id: int = Field(..., gt=0, description="Target employee ID of the new assignee")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Business justification for reassigning the task (minimum 10 characters)",
    )


class TaskResponse(BaseModel):
    """View model for a task entity."""
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    project_id: int
    milestone_id: Optional[int] = None
    team_id: Optional[int] = None
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: PriorityLevel
    status: TaskStatus
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


# ==========================================
# Task Submission Schemas (US-11)
# ==========================================

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
