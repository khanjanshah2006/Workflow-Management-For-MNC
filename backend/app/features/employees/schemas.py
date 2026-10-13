from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import CommonStatus, UserType


class DepartmentSummary(BaseModel):
    """Department basic details."""
    model_config = ConfigDict(from_attributes=True)

    dept_id: int
    name: str


class EmployeeCreate(BaseModel):
    """Payload to register a new employee and user account (US-04)."""
    full_name: str = Field(..., min_length=2, max_length=150, description="Full name of employee")
    email: EmailStr = Field(..., description="Unique corporate email address")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    designation: str = Field(..., min_length=2, max_length=100, description="Job title / role")
    dept_id: Optional[int] = Field(None, description="Department ID the employee belongs to")
    date_of_joining: date = Field(..., description="Official date of joining")
    initial_password: Optional[str] = Field(
        None, min_length=6, max_length=100, description="Optional custom initial password; auto-generated if omitted"
    )
    user_type: Optional[UserType] = Field(
        default=UserType.EMPLOYEE, description="System user role (EMPLOYEE, PM, HR, ADMIN)"
    )


class EmployeeStatusUpdate(BaseModel):
    """Payload to update employment status (ACTIVE / INACTIVE)."""
    status: CommonStatus = Field(..., description="Target employment status")


class EmployeeSummaryResponse(BaseModel):
    """Summary item for employee directory browsing."""
    model_config = ConfigDict(from_attributes=True)

    emp_id: int
    emp_code: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    designation: str
    dept_id: Optional[int] = None
    department_name: Optional[str] = None
    status: CommonStatus
    date_of_joining: date


class EmployeeDetailResponse(BaseModel):
    """Full detailed employee view."""
    model_config = ConfigDict(from_attributes=True)

    emp_id: int
    account_id: Optional[UUID] = None
    emp_code: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    designation: str
    dept_id: Optional[int] = None
    department: Optional[DepartmentSummary] = None
    status: CommonStatus
    date_of_joining: date
    initial_password: Optional[str] = Field(
        None, description="Initial temporary password returned on creation only"
    )
