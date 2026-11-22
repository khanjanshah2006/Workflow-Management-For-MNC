from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import TeamStatus


class DepartmentBase(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Unique name of the department (2-100 characters)",
        examples=["Engineering"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional detailed description of the department",
        examples=["Handles core product engineering and infrastructure"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Department name cannot be blank or whitespace-only")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def validate_and_strip_description(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Updated department name (2-100 characters)",
        examples=["Product Engineering"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated department description",
        examples=["Updated focus to include product design and engineering"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("Department name cannot be null")
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Department name cannot be blank or whitespace-only")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def validate_and_strip_description(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "DepartmentUpdate":
        if not self.model_fields_set:
            raise ValueError(
                "At least one field ('name' or 'description') must be provided for update"
            )
        return self


class DepartmentResponse(BaseModel):
    dept_id: int = Field(
        ...,
        description="Unique identifier of the department",
        examples=[1],
    )
    name: str = Field(
        ...,
        description="Unique name of the department",
        examples=["Engineering"],
    )
    description: str | None = Field(
        default=None,
        description="Optional detailed description of the department",
        examples=["Handles core product engineering and infrastructure"],
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the department was created",
    )
    team_count: int = Field(
        default=0,
        ge=0,
        description="Total number of distinct teams associated with this department (via team members and leads)",
        examples=[3],
    )

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Team Members & Tasks Schemas (US-37)
# ==========================================


class TeamMemberOut(BaseModel):
    """
    Response schema for an active team member roster entry.

    Conforms to US-37 Technical Scope:
    employee_id, emp_code, full_name, email, designation.
    """

    model_config = ConfigDict(from_attributes=True)

    employee_id: int = Field(
        ...,
        description="Unique employee identifier",
        examples=[1],
    )
    emp_code: str = Field(
        ...,
        description="Employee corporate identifier code",
        examples=["EMP001"],
    )
    full_name: str = Field(
        ...,
        description="Full display name of the employee",
        examples=["Alice Johnson"],
    )
    email: str = Field(
        ...,
        description="Official company email address",
        examples=["alice.johnson@company.com"],
    )
    designation: str = Field(
        ...,
        description="Employee designation or functional role",
        examples=["Senior Backend Engineer"],
    )


# ==========================================
# Department Team Schemas (US-05, Issue #141)
# ==========================================


class DepartmentTeamCreate(BaseModel):
    """Payload to create a new department team with designated lead and initial members."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Team name (unique per department, case-insensitive)",
        examples=["Payments Squad"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Scope of team responsibility",
        examples=["Card and wallet integrations"],
    )
    lead_emp_id: int = Field(
        ...,
        description="Employee ID designated as team lead (must be active)",
        examples=[21],
    )
    member_emp_ids: list[int] = Field(
        default_factory=list,
        description="List of employee IDs assigned as team members",
        examples=[[16, 18, 19]],
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Team name cannot be blank or whitespace-only")
        return v


class DepartmentTeamUpdate(BaseModel):
    """Payload for partial update of a team."""
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        description="Updated team name (unique per department)",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated team description",
    )
    lead_emp_id: int | None = Field(
        default=None,
        description="New team lead employee ID",
    )
    status: TeamStatus | None = Field(
        default=None,
        description="Updated team status (ACTIVE or DISBANDED)",
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Team name cannot be blank or whitespace-only")
        return v


class DepartmentTeamMemberAdd(BaseModel):
    """Payload to add members to a team."""
    emp_ids: list[int] = Field(
        ...,
        min_length=1,
        description="List of employee IDs to add as members",
        examples=[[16, 18]],
    )


class DepartmentTeamResponse(BaseModel):
    """Detailed view of a department team including lead name and member roster."""
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    dept_id: int | None = None
    project_id: int | None = None
    name: str
    description: str | None = None
    lead_emp_id: int | None = None
    lead_name: str | None = None
    status: TeamStatus
    created_at: datetime
    member_count: int = 0
    members: list[TeamMemberOut] = Field(default_factory=list)


class DepartmentTeamListItem(BaseModel):
    """Summary view of a department team in department listings."""
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    dept_id: int | None = None
    project_id: int | None = None
    name: str
    description: str | None = None
    lead_emp_id: int | None = None
    lead_name: str | None = None
    status: TeamStatus
    created_at: datetime
    member_count: int = 0


