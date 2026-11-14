"""
Pydantic V2 request/response schemas for the Client Portal feature (US-20, US-21, US-22).

These schemas are intentionally limited to high-level project, milestone,
and client-facing deliverable information.  Internal employee details, task
assignments, salaries, and internal comments are never exposed.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import FeedbackDecision


# ------------------------------------------------------------------
# Milestone-level schemas
# ------------------------------------------------------------------

class MilestoneSummaryCount(BaseModel):
    """Aggregate milestone counts shown alongside each project."""

    total: int = Field(..., description="Total milestones (non-deleted)")
    completed: int = Field(..., description="Milestones with status 'completed'")
    pending: int = Field(..., description="Milestones with status 'pending'")


class ClientMilestoneResponse(BaseModel):
    """Single milestone visible to the external client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: Optional[str] = None
    target_date: date
    status: str
    completed_at: Optional[datetime] = None


# ------------------------------------------------------------------
# Project-level schemas
# ------------------------------------------------------------------

class ClientProjectSummaryResponse(BaseModel):
    """
    Project summary returned on the client portal listing endpoint.

    Fields are deliberately restricted – ``pm_id``, employee allocations,
    internal notes, and task-level data are redacted.
    """

    model_config = ConfigDict(from_attributes=True)

    project_id: int
    project_code: str
    name: str
    description: Optional[str] = None
    status: str
    start_date: date
    target_end_date: Optional[date] = Field(
        None,
        description="Mapped from Project.end_date for client-friendly naming",
    )
    completion_pct: float = Field(
        ...,
        description="Percentage of milestones completed (0.0 – 100.0)",
    )
    milestones_summary: MilestoneSummaryCount


# ------------------------------------------------------------------
# Client Visibility Toggle schemas (US-42)
# ------------------------------------------------------------------

class ClientVisibilityUpdate(BaseModel):
    """Payload to toggle whether team member names/roles are visible to clients."""

    is_team_visible_to_client: bool = Field(
        ...,
        description="Whether individual team member names and designations are visible in client exports.",
    )


class ClientVisibilityResponse(BaseModel):
    """Response after updating a project's client visibility setting."""

    model_config = ConfigDict(from_attributes=True)

    project_id: int
    project_code: str
    name: str
    is_team_visible_to_client: bool


# ------------------------------------------------------------------
# Deliverable & Signoff schemas (US-22)
# ------------------------------------------------------------------

class DeliverableCreateIn(BaseModel):
    """Payload for a PM or Admin to publish a client-facing deliverable."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=4000)
    file_url: str = Field(..., min_length=1, max_length=2000)
    milestone_id: Optional[int] = Field(None, ge=1)
    version: Optional[int] = Field(None, ge=1)

    @field_validator("title", "file_url")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None


class DeliverableFeedbackIn(BaseModel):
    """Payload for a client to accept or request changes on a deliverable."""

    decision: FeedbackDecision
    comments: Optional[str] = Field(None, max_length=4000)
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, v):
        if isinstance(v, str):
            return FeedbackDecision(v.strip().upper())
        return v

    @field_validator("comments")
    @classmethod
    def strip_comments(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @model_validator(mode="after")
    def require_comments_when_changes_requested(self) -> "DeliverableFeedbackIn":
        if self.decision == FeedbackDecision.CHANGES_REQUESTED and not self.comments:
            raise ValueError(
                "Comments are mandatory when requesting changes on a deliverable"
            )
        return self


class DeliverableFeedbackOut(BaseModel):
    """Recorded client feedback entry for a deliverable."""

    model_config = ConfigDict(from_attributes=True)

    feedback_id: int
    deliverable_id: int
    decision: str
    comments: Optional[str] = None
    rating: int
    given_at: datetime


class DeliverableOut(BaseModel):
    """
    Client-facing deliverable view with version, signoff status, and feedback.

    Internal ``submitted_by`` employee IDs are omitted to preserve redaction.
    """

    model_config = ConfigDict(from_attributes=True)

    deliverable_id: int
    project_id: int
    milestone_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    file_url: str
    version: int
    submitted_at: datetime
    status: str
    feedbacks: List[DeliverableFeedbackOut] = Field(default_factory=list)

