"""Pydantic schemas for the leave feature (US-16, US-40, S4-BE-1)."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class PendingLeaveQueueItem(BaseModel):
    leave_id: int
    employee_id: int
    employee_name: str
    leave_type_name: str
    start_date: date
    end_date: date
    total_days: int
    reason: str
    status: LeaveStatus
    applied_at: datetime
    conflicting_task_count: int


class PendingLeaveQueueResponse(BaseModel):
    items: List[PendingLeaveQueueItem]
    total: int
    page: int
    limit: int


class LeaveApprovalPayload(BaseModel):
    review_remarks: Optional[str] = Field(None, max_length=2000)

    @field_validator("review_remarks")
    @classmethod
    def trim_optional_remarks(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class LeaveRejectionPayload(BaseModel):
    review_remarks: str = Field(..., min_length=1, max_length=2000)

    @field_validator("review_remarks")
    @classmethod
    def require_meaningful_remarks(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Review remarks must contain at least 10 non-whitespace characters.")
        return value
