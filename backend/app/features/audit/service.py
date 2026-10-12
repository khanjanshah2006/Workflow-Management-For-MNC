import math
from sqlalchemy.orm import Session

from app.features.audit.repository import AuditRepository
from app.features.audit.schemas import (
    AuditLogFilter,
    AuditLogPaginationResponse,
    AuditLogResponse,
)


class AuditService:
    """Service layer for business logic surrounding audit log inspection."""

    @staticmethod
    def get_audit_logs(db: Session, filters: AuditLogFilter) -> AuditLogPaginationResponse:
        items, total = AuditRepository.get_audit_logs(db=db, filters=filters)

        total_pages = math.ceil(total / filters.limit) if total > 0 else 0

        return AuditLogPaginationResponse(
            items=[AuditLogResponse.model_validate(item) for item in items],
            total=total,
            page=filters.page,
            limit=filters.limit,
            total_pages=total_pages,
        )
