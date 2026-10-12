from typing import List, Tuple
from sqlalchemy.orm import Session

from app.features.audit.schemas import AuditLogFilter
from app.models.audit_log import AuditLog


class AuditRepository:
    """Repository layer for querying and filtering the audit_log table."""

    @staticmethod
    def get_audit_logs(db: Session, filters: AuditLogFilter) -> Tuple[List[AuditLog], int]:
        query = db.query(AuditLog)

        if filters.entity_name:
            query = query.filter(AuditLog.entity_name.ilike(f"%{filters.entity_name.strip()}%"))

        if filters.action:
            query = query.filter(AuditLog.action == filters.action)

        if filters.start_date:
            query = query.filter(AuditLog.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(AuditLog.created_at <= filters.end_date)

        total = query.count()

        offset = (filters.page - 1) * filters.limit
        items = (
            query.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(filters.limit)
            .all()
        )

        return items, total
