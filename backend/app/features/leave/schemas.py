"""Pydantic schemas for the leave feature (US-16, US-17, US-40, S4-BE-1, S4-BE-3)."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import LeaveStatus


# ── US-16 / S4-BE-1 Schemas ──────────────────────────────────────────────────

class LeaveRequestCreate(BaseModel):
    """Payload for submitting a leave request."""
    leave_type_id: int = Field(..., description="ID of the leave type being requested")
    start_date: date = Field(..., description="Start date of leave (inclusive)")
    end_date: date = Field(..., description="End date of leave (inclusive)")
    reason: str = Field(..., description="Reason for leave (10 to 2000 chars stripped)")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if v is None:
            raise ValueError("Reason is required")
        stripped = v.strip()
        if len(stripped) < 10 or len(stripped) > 2000:
            raise ValueError("Reason must be between 10 and 2000 characters")
        return stripped


class LeaveRequestOut(BaseModel):
    """Leave request response representation."""
    leave_id: int
    emp_id: int
    leave_type_id: int
    leave_type_name: Optional[str] = None
    start_date: date
    end_date: date
    total_days: int
    reason: str
    status: LeaveStatus
    applied_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by_account_id: Optional[UUID] = None
    review_remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedLeaveRequestsOut(BaseModel):
    """Paginated leave requests history response."""
    items: List[LeaveRequestOut]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class LeaveBalanceItem(BaseModel):
    """Leave balance calculation representation for a single active leave type."""
    leave_type_id: int
    leave_type_name: str
    yearly_quota: int
    used_days: int
    pending_days: int
    available_days: int
    is_paid: bool

    model_config = ConfigDict(from_attributes=True)


LeaveBalanceOut = LeaveBalanceItem


class EmployeeLeaveBalanceResponse(BaseModel):
    """Wrapped year-wise leave balances response."""
    employee_id: int
    year: int
    balances: List[LeaveBalanceItem]

    model_config = ConfigDict(from_attributes=True)


# ── US-17 / S4-BE-3 Schemas ──────────────────────────────────────────────────

class ConflictingTaskItem(BaseModel):
    """Details of a task assigned to applicant due during the leave window (US-17)."""
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    title: str
    priority: str
    status: str
    due_date: date
    project_id: int
    milestone_id: Optional[int] = None
    milestone_title: Optional[str] = None


class MilestoneConflictItem(BaseModel):
    """Details of a pending milestone occurring during the leave window on applicant projects (US-17)."""
    model_config = ConfigDict(from_attributes=True)

    milestone_id: int
    title: str
    project_id: int
    target_date: date
    open_tasks_assigned_to_applicant: int


class TeamCoverageItem(BaseModel):
    """Teammate workload and availability during the leave window for potential reassignment (US-17)."""
    model_config = ConfigDict(from_attributes=True)

    emp_id: int
    full_name: str
    active_tasks_count: int
    has_leave_overlap: bool
    has_pending_leave_overlap: bool
    is_available_for_reassignment: bool


class LeaveConflictReportOut(BaseModel):
    """Consolidated conflict report for a leave request evaluation (US-17)."""
    model_config = ConfigDict(from_attributes=True)

    leave_id: int
    employee_id: int
    employee_name: str
    leave_type_name: str
    status: str
    start_date: date
    end_date: date
    total_days: int
    has_conflicts: bool
    conflicting_tasks: List[ConflictingTaskItem] = Field(default_factory=list)
    milestone_conflicts: List[MilestoneConflictItem] = Field(default_factory=list)
    team_coverage: List[TeamCoverageItem] = Field(default_factory=list)
    availability_threshold: int = 5
