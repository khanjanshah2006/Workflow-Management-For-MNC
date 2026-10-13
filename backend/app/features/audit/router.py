from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.audit.schemas import (
    AuditLogFilter,
    AuditLogPaginationResponse,
)
from app.features.audit.service import AuditService
from app.models.enums import AuditAction
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=AuditLogPaginationResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect audit logs (Admin only)",
    description="Retrieve paginated system audit trail events with optional filtering by entity, action, and date range.",
)
def get_audit_logs(
    entity_name: Optional[str] = Query(None, description="Filter by entity name (e.g. USER_ACCOUNT, PROJECT)"),
    action: Optional[AuditAction] = Query(None, description="Filter by action (CREATE, UPDATE, DELETE, LOGIN, APPROVE)"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: UserAccount = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
) -> AuditLogPaginationResponse:
    """
    Administrator endpoint to inspect enterprise audit logs.
    Restricted to accounts with ADMIN user_type.
    """
    filters = AuditLogFilter(
        entity_name=entity_name,
        action=action,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )

    return AuditService.get_audit_logs(db=db, filters=filters)
