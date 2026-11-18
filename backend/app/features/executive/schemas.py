"""
Pydantic V2 request/response schemas for Executive Dashboard & Analytics (US-24, S7).

Strictly read-only; absolutely no employee PII (full name, email, phone, salary) is exposed.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectsByStatus(BaseModel):
    """Breakdown of project counts by lifecycle status."""
    PLANNED: int = 0
    ACTIVE: int = 0
    ON_HOLD: int = 0
    COMPLETED: int = 0
    CANCELLED: int = 0


class TaskKpis(BaseModel):
    """High-level task metrics across the organization."""
    open_tasks: int = Field(0, description="Tasks in TODO, IN_PROGRESS, IN_REVIEW, BLOCKED, or REJECTED status")
    overdue_tasks: int = Field(0, description="Open tasks where due_date < current date/time")
    completed_last_30_days: int = Field(0, description="Tasks completed in the past 30 days")


class DepartmentSummaryItem(BaseModel):
    """High-level project and employee roll-up for a single department or Unassigned bucket."""
    dept_id: Optional[int] = Field(None, description="Department ID, or null for projects without department attribution")
    dept_name: str = Field(..., description="Department name, or 'Unassigned'")
    total_projects: int = 0
    active_projects: int = 0
    at_risk_projects: int = 0
    total_employees: int = 0
    milestone_velocity_pct: float = Field(0.0, description="Percentage of milestones completed (0.0 to 100.0, 1 decimal)")


class ExecutiveOverviewResponse(BaseModel):
    """Response schema for GET /api/v1/executive/dashboard."""
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    total_projects: int
    projects_by_status: ProjectsByStatus
    active_projects: int
    delayed_projects: int
    completed_projects: int
    overall_milestone_velocity_pct: float
    task_kpis: TaskKpis
    total_employees: int
    department_summaries: List[DepartmentSummaryItem] = Field(default_factory=list)


# ------------------------------------------------------------------
# Department Drilldown Schemas
# ------------------------------------------------------------------

class DepartmentProjectItem(BaseModel):
    """Project metrics within a department."""
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    project_code: str
    name: str
    status: str
    task_completion_pct: int = Field(0, description="Percentage of tasks completed (0 to 100)")
    milestones_completed: int = 0
    milestones_total: int = 0
    is_delayed: bool = False
    team_count: int = 0
    assigned_headcount: int = Field(0, description="Distinct active employees assigned to project")


class DepartmentTeamItem(BaseModel):
    """Team metrics under projects attributed to this department."""
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    name: str
    project_name: str
    member_count: int = 0
    open_tasks: int = 0


class DepartmentResourceAllocation(BaseModel):
    """Staffing metrics for all active employees within a department."""
    total_employees: int
    allocated_employees: int
    unallocated_employees: int
    headcount_by_designation: Dict[str, int] = Field(default_factory=dict)


class ExecutiveDepartmentDrilldownResponse(BaseModel):
    """Response schema for GET /api/v1/executive/dashboard/departments/{id}."""
    model_config = ConfigDict(from_attributes=True)

    dept_id: int
    dept_name: str
    projects: List[DepartmentProjectItem] = Field(default_factory=list)
    teams: List[DepartmentTeamItem] = Field(default_factory=list)
    resource_allocation: DepartmentResourceAllocation
