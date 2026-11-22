from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    CommonStatus,
    SkillProficiency,
    SkillRequestAction,
    SkillRequestStatus,
)


class DepartmentInfo(BaseModel):
    """Department summary for employee profile."""
    model_config = ConfigDict(from_attributes=True)

    dept_id: int
    name: str
    description: Optional[str] = None


class ManagerInfo(BaseModel):
    """Manager/lead summary for employee profile."""
    model_config = ConfigDict(from_attributes=True)

    emp_id: int
    emp_code: str
    full_name: str
    email: EmailStr
    designation: str


class ProfileResponse(BaseModel):
    """Detailed employee profile response."""
    model_config = ConfigDict(from_attributes=True)

    emp_id: int
    account_id: Optional[UUID] = None
    emp_code: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    designation: str
    date_of_joining: date
    status: CommonStatus
    department: Optional[DepartmentInfo] = None
    manager: Optional[ManagerInfo] = None
    emergency_contact: Optional[str] = None
    bio: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """Editable profile fields for employee self-service (US-03)."""
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    address: Optional[str] = Field(None, max_length=255, description="Residential contact address")
    emergency_contact: Optional[str] = Field(None, max_length=100, description="Emergency contact person and number")
    bio: Optional[str] = Field(None, max_length=500, description="Short personal biography")


class SkillResponse(BaseModel):
    """Skill response item with proficiency and years of experience."""
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    name: str
    category: str
    proficiency: SkillProficiency
    years_of_experience: int


# ── Skill Change Requests (US-34) ─────────────────────────────────────────────

class SkillChangeRequestCreate(BaseModel):
    """Payload for proposing a skill addition, update, or removal (US-34)."""
    action: SkillRequestAction = Field(..., description="Action: ADD, UPDATE, or REMOVE")
    skill_id: Optional[int] = Field(None, description="Existing skill ID (required for UPDATE/REMOVE)")
    proposed_skill_name: Optional[str] = Field(None, max_length=100, description="New skill name (for ADD when skill_id is not yet registered)")
    proficiency: Optional[SkillProficiency] = Field(None, description="Proficiency level (required for ADD and UPDATE)")
    years_of_experience: int = Field(default=0, ge=0, description="Years of experience with the skill")
    justification: Optional[str] = Field(None, max_length=1000, description="Reason for proposing the change")


class SkillChangeDecisionIn(BaseModel):
    """Decision payload for approving or rejecting a skill request (US-34)."""
    remarks: Optional[str] = Field(None, max_length=1000, description="Remarks (mandatory when rejecting)")


class SkillChangeRequestOut(BaseModel):
    """Response representation of a skill change request (US-34)."""
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    emp_id: int
    employee_name: Optional[str] = None
    action: SkillRequestAction
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    proposed_skill_name: Optional[str] = None
    proficiency: Optional[SkillProficiency] = None
    years_of_experience: int = 0
    justification: Optional[str] = None
    status: SkillRequestStatus
    remarks: Optional[str] = None
    reviewed_by_account_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class PaginatedSkillChangeRequestsOut(BaseModel):
    """Paginated list of skill change requests (US-34)."""
    model_config = ConfigDict(from_attributes=True)

    items: List[SkillChangeRequestOut]
    total: int
    page: int
    limit: int
