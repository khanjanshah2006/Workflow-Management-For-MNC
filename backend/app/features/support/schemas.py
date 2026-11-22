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
    reporter_name: Optional[str] = None
    assignee_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    activities: Optional[List[TicketActivityOut]] = []

    model_config = ConfigDict(from_attributes=True)


class TicketListOut(BaseModel):
    total: int
    tickets: List[TicketOut]


# -----------------------------------------------------------------------------
# S8-BE-2: IT Support Triage Queue, Status Workflow & Assignment Schemas
# -----------------------------------------------------------------------------

class TicketAssignRequest(BaseModel):
    """Payload for PUT /api/v1/support/tickets/{id}/assign."""
    assignee_account_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("assignee_account_id", "assigned_to", "assigned_to_emp_id", "assignee_id"),
        description="UserAccount UUID of the IT staff member being assigned",
    )

    model_config = ConfigDict(populate_by_name=True)


class TicketNoteRequest(BaseModel):
    """Payload for POST /api/v1/support/tickets/{id}/notes."""
    note: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        validation_alias=AliasChoices("note", "note_text"),
        description="Internal troubleshooting note (1–2000 characters)",
    )

    model_config = ConfigDict(populate_by_name=True)


class TicketStatusUpdateRequest(BaseModel):
    """Payload for PUT /api/v1/support/tickets/{id}/status."""
    status: str = Field(..., description="Target status: open, in_progress, resolved, closed")
    resolution_note: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("resolution_note", "resolution_notes"),
        description="Resolution explanation (mandatory when transitioning to 'resolved')",
    )

    model_config = ConfigDict(populate_by_name=True)


class SupportQueueItem(BaseModel):
    """Summary item for IT support triage queue listing."""
    id: int
    ticket_number: str
    subject: str
    category: str
    priority: str
    status: str
    reporter_name: Optional[str] = None
    assignee_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SupportQueueResponse(BaseModel):
    """Paginated triage queue response for GET /api/v1/support/tickets."""
    items: List[SupportQueueItem] = []
    total: int
    page: int
    limit: int
    tickets: Optional[List[SupportQueueItem]] = None

    @model_validator(mode="after")
    def sync_tickets_alias(self) -> "SupportQueueResponse":
        if self.tickets is None:
            self.tickets = self.items
        return self

    model_config = ConfigDict(from_attributes=True)


class SupportQueueMetricsResponse(BaseModel):
    """Summary counts by status and unassigned for support dashboard header."""
    open: int = 0
    in_progress: int = 0
    resolved: int = 0
    closed: int = 0
    escalated: int = 0
    unassigned: int = 0
    total: int = 0

    model_config = ConfigDict(from_attributes=True)

