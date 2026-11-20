"""Pydantic schemas for the leave feature (US-16, US-40, S4-BE-1)."""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LeaveStatus


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


# ==========================================
# Task Reallocation Schemas (US-14, US-19, S4-BE-5)
# ==========================================

class TaskReallocationActionType(str, Enum):
    REASSIGN = "REASSIGN"
    EXTEND_DEADLINE = "EXTEND_DEADLINE"


class TaskReallocationActionIn(BaseModel):
    task_id: int
    action_type: TaskReallocationActionType
    new_assignee_id: Optional[int] = None
    new_due_date: Optional[date] = None
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if v is None:
            raise ValueError("Reason is required")
        stripped = v.strip()
        if len(stripped) < 10 or len(stripped) > 500:
            raise ValueError("Reason must be between 10 and 500 characters")
        return stripped

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action_type == TaskReallocationActionType.REASSIGN:
            if self.new_assignee_id is None:
                raise ValueError("new_assignee_id is required for REASSIGN")
        elif self.action_type == TaskReallocationActionType.EXTEND_DEADLINE:
            if self.new_due_date is None:
                raise ValueError("new_due_date is required for EXTEND_DEADLINE")
        return self


class TaskReallocationBatchIn(BaseModel):
    actions: List[TaskReallocationActionIn] = Field(..., min_length=1, max_length=50)

    @field_validator("actions")
    @classmethod
    def validate_unique_task_ids(cls, v: List[TaskReallocationActionIn]) -> List[TaskReallocationActionIn]:
        ids = [a.task_id for a in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate task IDs in actions")
        return v


class ReassignedTaskOut(BaseModel):
    task_id: int
    from_emp_id: int
    to_emp_id: int

    model_config = ConfigDict(from_attributes=True)


class ExtendedDeadlineTaskOut(BaseModel):
    task_id: int
    old_due_date: date
    new_due_date: date

    model_config = ConfigDict(from_attributes=True)


class TaskReallocationBatchOut(BaseModel):
    leave_id: int
    reallocated_count: int
    reassigned: List[ReassignedTaskOut] = Field(default_factory=list)
    extended: List[ExtendedDeadlineTaskOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

