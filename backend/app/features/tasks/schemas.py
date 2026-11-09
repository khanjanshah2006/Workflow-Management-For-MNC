from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


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
