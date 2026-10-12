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
    entity_name: Optional[str] = None
    action: Optional[AuditAction] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class AuditLogPaginationResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    limit: int
    total_pages: int
