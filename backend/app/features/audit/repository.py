from typing import Generator, List, Tuple
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.features.audit.schemas import AuditLogFilter
from app.models.audit_log import AuditLog


class AuditRepository:
    """Repository layer for querying and filtering the audit_log table."""

    @classmethod
    def _build_filter_query(cls, db: Session, filters: AuditLogFilter):
        query = db.query(AuditLog)

        if filters.account_id:
            query = query.filter(AuditLog.account_id == filters.account_id)

        if filters.entity_name:
            query = query.filter(AuditLog.entity_name.ilike(f"%{filters.entity_name.strip()}%"))

        if filters.action:
            query = query.filter(AuditLog.action == filters.action)

        if filters.entity_ref_id:
            query = query.filter(AuditLog.entity_ref_id == filters.entity_ref_id.strip())

        if filters.ip_address:
            query = query.filter(AuditLog.ip_address == filters.ip_address.strip())

        if filters.start_date:
            query = query.filter(AuditLog.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(AuditLog.created_at <= filters.end_date)

        if filters.q:
            term = f"%{filters.q.strip()}%"
            query = query.filter(
                or_(
                    AuditLog.entity_name.ilike(term),
                    AuditLog.entity_ref_id.ilike(term),
                    AuditLog.old_value.ilike(term),
                    AuditLog.new_value.ilike(term),
                )
            )

        return query

    @classmethod
    def get_audit_logs(cls, db: Session, filters: AuditLogFilter) -> Tuple[List[AuditLog], int]:
        query = cls._build_filter_query(db, filters)
        total = query.count()

        offset = (filters.page - 1) * filters.limit
        items = (
            query.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(filters.limit)
            .all()
        )

        return items, total

    @classmethod
    def stream_audit_logs(cls, db: Session, filters: AuditLogFilter, chunk_size: int = 500) -> Generator[List[AuditLog], None, None]:
        query = cls._build_filter_query(db, filters).order_by(AuditLog.created_at.desc())
        offset = 0
        while True:
            chunk = query.offset(offset).limit(chunk_size).all()
            if not chunk:
                break
            yield chunk
            offset += len(chunk)
