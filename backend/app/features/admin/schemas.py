from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.enums import UserType


class UserAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    email: EmailStr
    user_type: UserType
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Minimum 6 characters")
    user_type: UserType


class UserAccountStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    user_type: UserType


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=6, description="New plain password, minimum 6 characters")


class UserAccountFilter(BaseModel):
    search: Optional[str] = None
    user_type: Optional[UserType] = None
    is_active: Optional[bool] = None
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class UserAccountPaginationResponse(BaseModel):
    items: List[UserAccountResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class BackupStatusResponse(BaseModel):
    status: str
    database: str
    last_verified_at: datetime
    active_connections: int
    details: str


# ==========================================
# System Parameters Schemas (US-46)
# ==========================================

class SystemParameterResponse(BaseModel):
    """View model for a system-wide configuration parameter."""
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    value_type: str
    description: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[UUID] = None


class SystemParameterUpdate(BaseModel):
    """Payload to update an operational parameter value."""
    value: str = Field(..., min_length=1, max_length=500, description="String representation of parameter value matching its type")


# ==========================================
# Time-Bound Elevated Access Schemas (US-45)
# ==========================================

class ElevatedAccessGrantCreate(BaseModel):
    """Payload to grant temporary elevated role privilege."""
    user_id: UUID = Field(..., description="Target user account UUID to elevate")
    granted_role: str = Field(..., min_length=2, max_length=50, description="Elevated role (e.g. PM, HR, ADMIN)")
    expires_at: datetime = Field(..., description="UTC timestamp when elevated access auto-expires (must be in future)")
    reason: str = Field(..., min_length=5, max_length=1000, description="Mandatory business justification for elevated privilege")


class ElevatedAccessGrantResponse(BaseModel):
    """View model for an elevated access grant record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    granted_role: str
    granted_by: UUID
    granted_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    reason: str


