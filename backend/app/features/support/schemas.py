from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


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
    reporter_id: Optional[int] = None
    assigned_to: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    activities: List[TicketActivityResponse] = []

    model_config = ConfigDict(from_attributes=True)

