"""
Pydantic V2 request/response schemas for Executive Dashboard & Analytics (US-24, S7).

Strictly read-only; absolutely no employee PII (full name, email, phone, salary) is exposed.
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReportFormat


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


# ------------------------------------------------------------------
# Executive Management Reports Schemas (US-25, S7-BE-2)
# ------------------------------------------------------------------

class ExecutiveReportCreateRequest(BaseModel):
    """Payload for POST /api/v1/executive/reports/generate."""
    report_title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Human-readable title for the report (3-255 characters)",
    )
    period_start: date = Field(..., description="Start date of the reporting period (YYYY-MM-DD)")
    period_end: date = Field(..., description="End date of the reporting period (YYYY-MM-DD)")
    format: ReportFormat = Field(
        ReportFormat.PDF,
        description="Desired export file format (PDF or CSV)",
    )
    include_department_breakdown: bool = Field(
        False,
        description="Whether to include granular department summaries in the PDF report",
    )


class ExecutiveReportResponse(BaseModel):
    """Metadata response for a generated executive management report."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    report_id: int
    report_title: str
    format: str
    period_start: date
    period_end: date
    include_department_breakdown: bool
    file_size_bytes: int
    generated_at: datetime
    download_url: str

    @classmethod
    def from_orm_report(cls, report: "ExecutiveReport") -> "ExecutiveReportResponse":
        fmt = (
            report.report_format.value
            if hasattr(report.report_format, "value")
            else str(report.report_format)
        )
        return cls(
            report_id=report.report_id,
            report_title=report.report_title,
            format=fmt,
            period_start=report.period_start,
            period_end=report.period_end,
            include_department_breakdown=report.include_department_breakdown,
            file_size_bytes=report.file_size_bytes,
            generated_at=report.generated_at,
            download_url=f"/api/v1/executive/reports/{report.report_id}/download",
        )


class PaginatedExecutiveReportsResponse(BaseModel):
    """Paginated report history for GET /api/v1/executive/reports."""
    model_config = ConfigDict(from_attributes=True)

    items: List[ExecutiveReportResponse] = Field(default_factory=list)
    total: int
    page: int
    limit: int

