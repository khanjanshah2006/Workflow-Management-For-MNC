from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TicketCreateIn(BaseModel):
    subject: Optional[str] = Field(None, min_length=3, max_length=255, description="Short subject describing the issue")
    title: Optional[str] = Field(None, min_length=3, max_length=255, description="Alias for subject")
    description: str = Field(..., min_length=5, description="Detailed problem description")
    category: Optional[str] = Field("other", description="hardware, software, network, access, other")
    priority: Optional[str] = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")

    @model_validator(mode="before")
    @classmethod
    def sync_subject_and_title(cls, data: dict):
        if isinstance(data, dict):
            subject_val = data.get("subject") or data.get("title")
            if not subject_val:
                raise ValueError("Either 'subject' or 'title' must be provided (min 3 characters).")
            data["subject"] = subject_val
            data["title"] = subject_val
        return data

    model_config = ConfigDict(from_attributes=True)


class TicketAssignIn(BaseModel):
    assigned_to: UUID = Field(..., description="UUID of the IT Support staff member account to assign")
    reassignment_reason: Optional[str] = Field(None, description="Optional explanation for assignment or reassignment")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TicketReassignIn(BaseModel):
    assigned_to: UUID = Field(..., description="UUID of the new IT Support assignee")
    reassignment_reason: Optional[str] = Field(None, description="Reason for reassigning ticket")

    model_config = ConfigDict(from_attributes=True)


class TicketNoteIn(BaseModel):
    note: str = Field(..., min_length=1, description="Troubleshooting or investigation note")

    model_config = ConfigDict(from_attributes=True)


class TicketStatusUpdateIn(BaseModel):
    status: str = Field(..., description="Target status: open, in_progress, resolved, escalated, closed")
    resolution_notes: Optional[str] = Field(None, description="Optional notes explaining status change or resolution")

    model_config = ConfigDict(from_attributes=True)


class TicketEscalateIn(BaseModel):
    reason: str = Field(..., min_length=5, description="Reason for escalation to higher-level support/admin")
    target_role: Optional[str] = Field("SYSTEM_ADMIN", description="Target role receiving escalation")

    model_config = ConfigDict(from_attributes=True)


class TicketActivityOut(BaseModel):
    id: int
    activity_id: int
    ticket_id: int
    actor_id: Optional[UUID] = None
    performed_by: Optional[UUID] = None
    action: str
    activity_type: str
    note: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketOut(BaseModel):
    id: int
    ticket_id: int
    ticket_number: str
    subject: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    reporter_id: UUID
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    activities: Optional[List[TicketActivityOut]] = []

    model_config = ConfigDict(from_attributes=True)


class TicketListOut(BaseModel):
    total: int
    tickets: List[TicketOut]

    model_config = ConfigDict(from_attributes=True)


class QueueMetricsOut(BaseModel):
    open_count: int
    in_progress_count: int
    resolved_count: int
    escalated_count: int
    unassigned_count: int
    total_tickets: int

    model_config = ConfigDict(from_attributes=True)
