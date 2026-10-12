import json
import logging
from typing import Any, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction

logger = logging.getLogger(__name__)


def _serialize_value(val: Any) -> str | None:
    """Serialize dictionary, list, or primitive to JSON string, or return string as is."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val, default=str)
    except Exception as exc:
        logger.warning("Could not JSON serialize audit log value: %s. Using str().", exc)
        return str(val)


def _parse_audit_action(action: Union[str, AuditAction]) -> AuditAction:
    """Parse string or enum into AuditAction enum safely."""
    if isinstance(action, AuditAction):
        return action

    action_clean = str(action).strip().upper()
    try:
        return AuditAction[action_clean]
    except KeyError:
        return AuditAction(action_clean)


def write_audit_log(
    db: Session,
    action: Union[str, AuditAction],
    entity_name: str,
    entity_ref_id: Any,
    account_id: Union[UUID, str, None] = None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
) -> None:
    """
    Synchronous helper to record an audit log event.
    Guaranteed not to raise an exception or abort the primary transaction.
    """
    try:
        # Normalize UUID
        parsed_account_id = None
        if account_id:
            parsed_account_id = UUID(str(account_id)) if not isinstance(account_id, UUID) else account_id

        # Normalize Action Enum
        action_enum = _parse_audit_action(action)

        # Create record
        audit_entry = AuditLog(
            account_id=parsed_account_id,
            action=action_enum,
            entity_name=str(entity_name),
            entity_ref_id=str(entity_ref_id),
            old_value=_serialize_value(old_value),
            new_value=_serialize_value(new_value),
            ip_address=ip_address,
        )

        # Use savepoint so any audit failure rolls back only itself
        with db.begin_nested():
            db.add(audit_entry)
        db.commit()
    except Exception as exc:
        logger.error("Failed to write audit log event: %s", exc, exc_info=True)


async def log_audit_event(
    db: Session,
    action: str,          # "CREATE", "UPDATE", "DELETE", "LOGIN", "APPROVE"
    entity_name: str,     # e.g., "PROJECT", "TASK", "DEPARTMENT", "EMPLOYEE"
    entity_ref_id: str,   # ID of affected entity
    account_id: UUID,     # User who performed the action
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Asynchronous audit logging service helper.
    Wraps DB insert in a resilient try...except block so it never crashes
    the primary business operation.
    """
    write_audit_log(
        db=db,
        action=action,
        entity_name=entity_name,
        entity_ref_id=entity_ref_id,
        account_id=account_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
