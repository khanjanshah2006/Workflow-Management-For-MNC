import json
import logging
from typing import Any, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction

logger = logging.getLogger(__name__)
_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "new_password",
    "old_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "mfa_secret",
    "credentials",
    "api_key",
    "secret_key",
}


def _is_sensitive_key(key: Any) -> bool:
    """Return True if key name matches any known credential or secret pattern."""
    k = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    if k in _SENSITIVE_KEYS:
        return True
    return any(pattern in k for pattern in ("password", "secret", "token", "credential", "api_key"))


def _redact_data(val: Any) -> Any:
    """Recursively redact sensitive keys from nested dicts, lists, and collections."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            key_str = str(k)
            if isinstance(v, (dict, list, tuple, set)):
                sanitized[key_str] = _redact_data(v)
            elif _is_sensitive_key(key_str):
                sanitized[key_str] = "[REDACTED]"
            else:
                sanitized[key_str] = v
        return sanitized
    elif isinstance(val, (list, tuple, set)):
        return [_redact_data(item) for item in val]
    return val


def _serialize_value(val: Any) -> str | None:
    """Serialize values to JSON while recursively redacting credentials and secrets."""
    if val is None:
        return None
    if isinstance(val, str):
        # If it's a JSON string representing a dict or list, parse and redact recursively
        val_trimmed = val.strip()
        if (val_trimmed.startswith("{") and val_trimmed.endswith("}")) or (
            val_trimmed.startswith("[") and val_trimmed.endswith("]")
        ):
            try:
                parsed = json.loads(val_trimmed)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(_redact_data(parsed), default=str)
            except Exception:
                pass
        return val
    try:
        sanitized = _redact_data(val)
        return json.dumps(sanitized, default=str)
    except Exception as exc:
        logger.warning("Could not JSON serialize audit log value: %s", exc)
        return str(val)


def _parse_audit_action(action: Union[str, AuditAction]) -> AuditAction:
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
    commit: bool = True,
) -> bool:
    """Write an audit row. Set commit=False to leave transaction ownership to caller."""
    try:
        parsed_account_id = None
        if account_id:
            parsed_account_id = account_id if isinstance(account_id, UUID) else UUID(str(account_id))
        audit_entry = AuditLog(
            account_id=parsed_account_id,
            action=_parse_audit_action(action),
            entity_name=str(entity_name),
            entity_ref_id=str(entity_ref_id),
            old_value=_serialize_value(old_value),
            new_value=_serialize_value(new_value),
            ip_address=ip_address,
        )
        with db.begin_nested():
            db.add(audit_entry)
            db.flush()
        if commit:
            db.commit()
        return True
    except Exception as exc:
        logger.error("Failed to write audit log event: %s", exc, exc_info=True)
        # A failed nested transaction must be cleared before the session is reused.
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("Failed to recover database session after audit error")
        return False


async def log_audit_event(
    db: Session,
    action: str,
    entity_name: str,
    entity_ref_id: str,
    account_id: UUID,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
) -> None:
    write_audit_log(
        db=db, action=action, entity_name=entity_name, entity_ref_id=entity_ref_id,
        account_id=account_id, old_value=old_value, new_value=new_value,
        ip_address=ip_address,
    )
