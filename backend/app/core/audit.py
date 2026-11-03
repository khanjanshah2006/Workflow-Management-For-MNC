from typing import Any, Optional, Union
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction


def write_audit_log(
    db: Session,
    actor: Any,
    action: Optional[Union[AuditAction, str]] = None,
    action_type: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_affected: Optional[str] = None,
    entity_ref_id: Optional[Union[str, int, UUID]] = None,
    entity_id: Optional[Union[str, int, UUID]] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Write an audit log entry complying with NFR-AU01-04.
    Supports both naming conventions (entity_name/entity_affected, action/action_type, entity_ref_id/entity_id).
    """
    # Resolve action
    resolved_action_str = str(action or action_type or "UPDATE").upper()
    try:
        resolved_action = AuditAction(resolved_action_str)
    except ValueError:
        resolved_action = AuditAction.UPDATE

    # Resolve entity name
    resolved_entity_name = str(entity_name or entity_affected or "UNKNOWN")

    # Resolve entity ref id
    resolved_entity_ref_id = str(entity_ref_id if entity_ref_id is not None else (entity_id or ""))

    # Resolve actor account_id
    account_id = None
    if actor is not None:
        if isinstance(actor, dict):
            account_id = actor.get("account_id")
        elif hasattr(actor, "account_id") and actor.account_id:
            account_id = actor.account_id
        elif hasattr(actor, "id") and isinstance(actor.id, UUID):
            account_id = actor.id

    log_entry = AuditLog(
        account_id=account_id,
        action=resolved_action,
        entity_name=resolved_entity_name,
        entity_ref_id=resolved_entity_ref_id,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        ip_address=ip_address,
    )
    db.add(log_entry)
    return log_entry

