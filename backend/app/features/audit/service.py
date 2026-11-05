import csv
import io
import math
from typing import Generator
from sqlalchemy.orm import Session

from app.features.audit.repository import AuditRepository
from app.features.audit.schemas import (
    AuditLogFilter,
    AuditLogPaginationResponse,
    AuditLogResponse,
)


class AuditService:
    """Service layer for business logic surrounding audit log inspection and export."""

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

    @staticmethod
    def export_audit_logs_csv(db: Session, filters: AuditLogFilter) -> Generator[str, None, None]:
        """
        Stream filtered audit log records as a CSV formatted file.
        Uses chunked querying to maintain constant memory consumption.
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Write header
        headers = [
            "log_id",
            "created_at",
            "account_id",
            "action",
            "entity_name",
            "entity_ref_id",
            "ip_address",
            "old_value",
            "new_value",
        ]
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Stream records
        for chunk in AuditRepository.stream_audit_logs(db, filters, chunk_size=500):
            for log in chunk:
                action_str = log.action.value if hasattr(log.action, "value") else str(log.action)
                created_at_str = log.created_at.isoformat() if log.created_at else ""
                writer.writerow([
                    log.log_id,
                    created_at_str,
                    str(log.account_id) if log.account_id else "",
                    action_str,
                    log.entity_name,
                    log.entity_ref_id,
                    log.ip_address or "",
                    log.old_value or "",
                    log.new_value or "",
                ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
