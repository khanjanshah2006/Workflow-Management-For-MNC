from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PriorityLevel, TaskStatus


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
