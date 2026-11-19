"""Pydantic schemas for the leave feature (US-16, US-40, S4-BE-1)."""
from datetime import date, datetime
from typing import Optional
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


class LeaveBalanceOut(BaseModel):
    """Leave balance calculation representation for a single active leave type."""
    leave_type_id: int
    leave_type_name: str
    yearly_quota: int
    used_days: int
    pending_days: int
    available_days: int

    model_config = ConfigDict(from_attributes=True)
