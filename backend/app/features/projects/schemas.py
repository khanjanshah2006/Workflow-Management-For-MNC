from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PriorityLevel, ProjectStatus, TeamStatus


# ==========================================
# Project Schemas
# ==========================================

class ProjectCreate(BaseModel):
    """Payload to create a new project (US-06)."""
    project_code: str = Field(..., min_length=2, max_length=50, description="Unique project code (e.g. PRJ-CORP-01)")
    name: str = Field(..., min_length=2, max_length=200, description="Project title")
    description: Optional[str] = Field(None, description="Detailed project description")
    start_date: date = Field(..., description="Planned project start date")
    end_date: Optional[date] = Field(None, description="Target completion date")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Priority level")
    client_id: int = Field(..., description="ID of commissioning client")
    pm_id: Optional[int] = Field(None, description="Optional PM ID (auto-resolved from logged-in PM if omitted)")


class ProjectResponse(BaseModel):
    """Project entity response view."""
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    project_code: str
    name: str
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    priority: PriorityLevel
    status: ProjectStatus
    client_id: int
    pm_id: int


# ==========================================
# Project Staffing / Assignment Schemas
# ==========================================

class ProjectAssignmentCreate(BaseModel):
    """Payload to assign an employee to a project roster (US-07)."""
    emp_id: int = Field(..., description="Employee ID to allocate to project")
    role_in_project: str = Field(..., min_length=2, max_length=100, description="Role in project (e.g. Lead Frontend Dev)")


class ProjectAssignmentResponse(BaseModel):
    """Project assignment record view."""
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    project_id: int
    emp_id: int
    role_in_project: str
    assigned_on: date
    released_on: Optional[date] = None


# ==========================================
# Team & Team Membership Schemas
# ==========================================

class TeamCreate(BaseModel):
    """Payload to create a functional team inside a project (US-07)."""
    name: str = Field(..., min_length=2, max_length=150, description="Team name (e.g. Backend Squad Alpha)")
    description: Optional[str] = Field(None, description="Scope of team responsibility")
    lead_emp_id: Optional[int] = Field(None, description="Employee ID designated as Team Lead")


class TeamResponse(BaseModel):
    """Team details view."""
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    project_id: Optional[int] = None
    lead_emp_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    status: TeamStatus
    created_at: datetime


class TeamMemberAdd(BaseModel):
    """Payload to add an allocated employee into a project team."""
    emp_id: int = Field(..., description="Employee ID (must be active on project assignment first)")


class TeamMemberResponse(BaseModel):
    """Team membership record view."""
    model_config = ConfigDict(from_attributes=True)

    team_member_id: int
    team_id: int
    emp_id: int
    joined_on: date
