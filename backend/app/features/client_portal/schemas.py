"""
Pydantic V2 response schemas for the Client Portal feature (US-20, US-21).

These schemas are intentionally limited to high-level project and milestone
information.  Internal employee details, task assignments, salaries, and
internal comments are never exposed.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

