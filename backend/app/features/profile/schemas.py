from datetime import date
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import CommonStatus, SkillProficiency


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


class ProfileUpdateRequest(BaseModel):
    """Editable profile fields for employee self-service (US-03)."""
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    address: Optional[str] = Field(None, max_length=255, description="Residential contact address")
    emergency_contact: Optional[str] = Field(None, max_length=100, description="Emergency contact person and number")


class SkillResponse(BaseModel):
    """Skill response item with proficiency and years of experience."""
    model_config = ConfigDict(from_attributes=True)

    skill_id: int
    name: str
    category: str
    proficiency: SkillProficiency
    years_of_experience: int
