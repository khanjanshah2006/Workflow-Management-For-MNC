from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DepartmentBase(BaseModel):
    """Shared department attributes for request payloads."""

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
        """Strip whitespace and reject blank or whitespace-only names."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Department name cannot be blank or whitespace-only")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def validate_and_strip_description(cls, v: Any) -> Any:
        """Strip whitespace from description; empty string converts to None."""
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class DepartmentCreate(DepartmentBase):
    """Payload schema for creating a new department."""

    pass


class DepartmentUpdate(BaseModel):
    """Payload schema for updating an existing department (PUT / PATCH)."""

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
        """Strip whitespace and reject blank or explicit null names."""
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
        """Strip whitespace from description; empty string converts to None."""
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "DepartmentUpdate":
        """Ensure at least one updatable field is provided."""
        if self.name is None and self.description is None:
            raise ValueError(
                "At least one field ('name' or 'description') must be provided for update"
            )
        return self


class DepartmentResponse(BaseModel):
    """Response schema returned to clients representing a department."""

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
        description="Total number of active teams in this department",
        examples=[3],
    )

    model_config = ConfigDict(from_attributes=True)
