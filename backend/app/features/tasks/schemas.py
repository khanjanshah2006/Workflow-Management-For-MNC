from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


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
