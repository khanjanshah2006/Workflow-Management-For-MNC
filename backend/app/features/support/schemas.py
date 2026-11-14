from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AliasChoices, model_validator


class EscalateTicketRequest(BaseModel):
    reason: str = Field(
        ...,
        validation_alias=AliasChoices("reason", "escalation_reason"),
        min_length=1,
        description="Reason for escalating the ticket to the System Administrator",
    )

    model_config = ConfigDict(populate_by_name=True)


class TicketActivityResponse(BaseModel):
    activity_id: int
    ticket_id: int
    activity_type: str
    details: Optional[str] = None
    actor_account_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketResponse(BaseModel):
    ticket_id: int
    ticket_number: str
    title: str
    description: str
    category: Optional[str] = None
    priority: str
    status: str
    escalation_reason: Optional[str] = None
    reporter_id: Optional[Any] = None
    assigned_to: Optional[Any] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    activities: List[TicketActivityResponse] = []

    model_config = ConfigDict(from_attributes=True)


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
    escalation_reason: Optional[str] = None
    reporter_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    activities: Optional[List[TicketActivityOut]] = []

    model_config = ConfigDict(from_attributes=True)


class TicketListOut(BaseModel):
    total: int
    tickets: List[TicketOut]
