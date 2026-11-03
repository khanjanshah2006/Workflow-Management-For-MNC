from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
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

admin_guard = require_role(["ADMIN"])


@router.get(
    "",
    response_model=AuditLogPaginationResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect and search audit logs (Admin only - US-30, US-47)",
    description="Retrieve paginated enterprise audit trail events with multi-field search and filtering.",
)
def get_audit_logs(
    account_id: Optional[UUID] = Query(None, description="Filter by user account UUID"),
    entity_name: Optional[str] = Query(None, description="Filter by entity name (e.g. USER_ACCOUNT, PROJECT)"),
    action: Optional[AuditAction] = Query(None, description="Filter by action (CREATE, UPDATE, DELETE, LOGIN, APPROVE)"),
    entity_ref_id: Optional[str] = Query(None, description="Filter by entity reference ID"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    q: Optional[str] = Query(None, description="Search term across entities and change diffs"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: UserAccount = Depends(admin_guard),
    db: Session = Depends(get_db),
) -> AuditLogPaginationResponse:
    """
    Administrator endpoint to inspect enterprise audit logs.
    Restricted to accounts with ADMIN user_type.
    """
    filters = AuditLogFilter(
        account_id=account_id,
        entity_name=entity_name,
        action=action,
        entity_ref_id=entity_ref_id,
        ip_address=ip_address,
        q=q,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )

    return AuditService.get_audit_logs(db=db, filters=filters)


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export audit logs to CSV (Admin only - US-47)",
    description="Stream filtered audit records as a CSV file download.",
)
def export_audit_logs(
    account_id: Optional[UUID] = Query(None, description="Filter by user account UUID"),
    entity_name: Optional[str] = Query(None, description="Filter by entity name"),
    action: Optional[AuditAction] = Query(None, description="Filter by action"),
    entity_ref_id: Optional[str] = Query(None, description="Filter by entity reference ID"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    q: Optional[str] = Query(None, description="Search term across entities and change diffs"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    current_user: UserAccount = Depends(admin_guard),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Export matching audit logs as a downloadable CSV.
    Logs an audit event recording the export action.
    """
    filters = AuditLogFilter(
        account_id=account_id,
        entity_name=entity_name,
        action=action,
        entity_ref_id=entity_ref_id,
        ip_address=ip_address,
        q=q,
        start_date=start_date,
        end_date=end_date,
        page=1,
        limit=1000,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"audit_logs_{timestamp}.csv"

    # Record sensitive export action in audit log
    write_audit_log(
        db=db,
        action=AuditAction.UPDATE,
        entity_name="AUDIT_LOG",
        entity_ref_id=filename,
        account_id=current_user.account_id,
        new_value={"action": "export_csv", "filters": filters.model_dump(mode="json", exclude_none=True)},
    )

    return StreamingResponse(
        AuditService.export_audit_logs_csv(db=db, filters=filters),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
