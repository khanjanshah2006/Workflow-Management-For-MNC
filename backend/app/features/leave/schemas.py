"""Pydantic schemas for the leave feature (S4)."""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


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
