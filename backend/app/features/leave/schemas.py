"""Pydantic schemas for the leave feature (US-16, US-18, US-40, S4-BE-1, S4-BE-2)."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import LeaveStatus


# ──────────────────────────────────────────────
# S4-BE-2  Leave Policy / Leave Type Schemas
# ──────────────────────────────────────────────

class LeavePolicyCreate(BaseModel):
    """Payload to create a new leave type / policy (HR only)."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Unique human-readable name, e.g. 'Annual Leave'",
    )
    yearly_quota: int = Field(
        ...,
        ge=0,
        le=365,
        description="Maximum days an employee can take per year (0 = unlimited carry-forward tracked externally)",
    )
    is_paid: bool = Field(default=True, description="Whether this leave type is paid")
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional human-readable description of the policy",
    )


class LeavePolicyUpdate(BaseModel):
    """Payload to update an existing leave type / policy (HR only).
    All fields are optional so callers can patch a single field.
    """
    yearly_quota: Optional[int] = Field(
        default=None,
        ge=0,
        le=365,
        description="New yearly quota; must be ≥ 0",
    )
    is_paid: Optional[bool] = Field(
        default=None,
        description="Update paid/unpaid classification",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Update the policy description",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Deactivate (soft-delete) or reactivate a policy",
    )


class LeavePolicyResponse(BaseModel):
    """Full view of a leave type / policy record."""
    model_config = ConfigDict(from_attributes=True)

    leave_type_id: int
    name: str
    yearly_quota: int
    is_paid: bool
    is_active: bool
    description: Optional[str] = None


class LeaveBalanceResponse(BaseModel):
    """Remaining leave days for a given leave type in the current year."""
    model_config = ConfigDict(from_attributes=True)

    leave_type_id: int
    leave_type_name: str
    yearly_quota: int
    used_days: int
    remaining_days: int


# ──────────────────────────────────────────────
# S4-BE-1  Leave Request Schemas
# ──────────────────────────────────────────────

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
    model_config = ConfigDict(from_attributes=True)

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


# Backwards compatibility alias for LeaveRequestOut
LeaveRequestResponse = LeaveRequestOut


class PaginatedLeaveRequestsOut(BaseModel):
    """Paginated leave requests history response."""
    model_config = ConfigDict(from_attributes=True)

    items: List[LeaveRequestOut]
    total: int
    page: int
    limit: int


class LeaveBalanceItem(BaseModel):
    """Leave balance calculation representation for a single active leave type."""
    model_config = ConfigDict(from_attributes=True)

    leave_type_id: int
    leave_type_name: str
    yearly_quota: int
    used_days: int
    pending_days: int
    available_days: int
    is_paid: bool


LeaveBalanceOut = LeaveBalanceItem


class EmployeeLeaveBalanceResponse(BaseModel):
    """Wrapped year-wise leave balances response."""
    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    year: int
    balances: List[LeaveBalanceItem]
