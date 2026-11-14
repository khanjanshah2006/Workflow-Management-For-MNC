from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import AuditAction


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    account_id: Optional[UUID] = None
    action: AuditAction
    entity_name: str
    entity_ref_id: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogFilter(BaseModel):
    account_id: Optional[UUID] = Field(default=None, description="Filter by user account UUID")
    entity_name: Optional[str] = Field(default=None, description="Filter by entity name (e.g. USER_ACCOUNT, PROJECT)")
    action: Optional[AuditAction] = Field(default=None, description="Filter by action (CREATE, UPDATE, DELETE, LOGIN, APPROVE)")
    entity_ref_id: Optional[str] = Field(default=None, description="Filter by affected entity reference ID")
    ip_address: Optional[str] = Field(default=None, description="Filter by client IP address")
    q: Optional[str] = Field(default=None, description="General search across entity name, ref ID, or values")
    start_date: Optional[datetime] = Field(default=None, description="Filter by start date (ISO format)")
    end_date: Optional[datetime] = Field(default=None, description="Filter by end date (ISO format)")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=1000, description="Items per page (max 1000)")


class AuditLogPaginationResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    limit: int
    total_pages: int
