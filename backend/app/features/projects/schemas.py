from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import PriorityLevel, ProjectStatus, TeamStatus, MilestoneStatus, CommonStatus
from app.features.employees.schemas import EmployeeWorkloadResponse


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


class ProjectStatusUpdate(BaseModel):
    """Requested lifecycle status for a project."""
    model_config = ConfigDict(extra="forbid")

    status: ProjectStatus = Field(..., examples=["ACTIVE"])


class ProjectStatusResponse(BaseModel):
    """Project status after a lifecycle transition."""
    project_id: int
    status: ProjectStatus


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


# ==========================================
# Milestone Schemas (US-08)
# ==========================================

class MilestoneCreate(BaseModel):
    """Payload to create a milestone within a project (US-08)."""
    title: str = Field(..., min_length=1, max_length=255, description="Milestone title")
    description: Optional[str] = Field(None, description="Detailed milestone description")
    target_date: date = Field(..., description="Target completion date for the milestone")
    status: Optional[MilestoneStatus] = Field(default=MilestoneStatus.PENDING, description="Milestone status ('pending', 'completed')")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Milestone title cannot be blank")
        return cleaned

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if v is None:
            return MilestoneStatus.PENDING
        if isinstance(v, str):
            clean = v.strip().lower()
            return MilestoneStatus(clean)
        return v


class MilestoneUpdate(BaseModel):
    """Payload to update an existing milestone (US-08)."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated milestone title")
    description: Optional[str] = Field(None, description="Updated milestone description")
    target_date: Optional[date] = Field(None, description="Updated target date")
    status: Optional[MilestoneStatus] = Field(None, description="Updated status ('pending' or 'completed')")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Milestone title cannot be blank")
        return cleaned

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip().lower()
            return MilestoneStatus(clean)
        return v


class MilestoneResponse(BaseModel):
    """Milestone record view (US-08)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: Optional[str] = None
    target_date: date
    status: MilestoneStatus
    completed_at: Optional[datetime] = None
    created_at: datetime


# ==========================================
# Eligible Employees & Workload Schemas (US-39)
# ==========================================

class EligibleEmployeeResponse(BaseModel):
    """Eligible employee with aggregated cross-project workload metrics (US-39)."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    emp_id: int = Field(..., description="Employee ID")
    employee_id: Optional[int] = Field(None, description="Employee ID alias")
    emp_code: str = Field(..., description="Employee code (EMP-XXXX)")
    full_name: str = Field(..., description="Full name of employee")
    email: str = Field(..., description="Corporate email address")
    phone: Optional[str] = Field(None, description="Phone number")
    designation: str = Field(..., description="Designation / job title")
    dept_id: Optional[int] = Field(None, description="Department ID")
    department_name: Optional[str] = Field(None, description="Department name")
    status: CommonStatus = Field(default=CommonStatus.ACTIVE, description="Employment status")
    date_of_joining: Optional[date] = Field(None, description="Date of joining")

    # Aggregated workload metrics
    active_projects_count: int = Field(default=0, description="Active projects count")
    open_tasks_count: int = Field(default=0, description="Open tasks count across all projects")
    utilization_pct: float = Field(default=0.0, description="Calculated utilization percentage")
    workload: Optional[EmployeeWorkloadResponse] = Field(None, description="Nested workload details")

    @model_validator(mode="before")
    @classmethod
    def sync_employee_ids_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            emp_id = data.get("emp_id") or data.get("employee_id")
            if emp_id is not None:
                data["emp_id"] = emp_id
                data["employee_id"] = emp_id
        return data

    @model_validator(mode="after")
    def sync_employee_ids_after(self) -> "EligibleEmployeeResponse":
        if self.employee_id is None:
            self.employee_id = self.emp_id
        if self.workload is None:
            self.workload = EmployeeWorkloadResponse(
                employee_id=self.emp_id,
                active_projects_count=self.active_projects_count,
                open_tasks_count=self.open_tasks_count,
                utilization_pct=self.utilization_pct,
            )
        return self


