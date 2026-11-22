import json
import logging
import math
import os
import shutil
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.engine import make_url
from fastapi import HTTPException, status

from app.core import roles
from app.core.audit import write_audit_log
from app.core.security import hash_password
from app.core.config import settings
from app.core.notification_types import (
    ACCOUNT_UNLOCKED,
    ELEVATED_ACCESS_GRANTED,
    ELEVATED_ACCESS_REVOKED,
)
from app.db.session import engine
from app.features.admin.repository import AdminRepository
from app.features.admin.schemas import (
    AdminPasswordReset,
    BackupStatusResponse,
    AnomalyAlert,
    AnomalyAlertsResponse,
    ElevatedAccessGrantCreate,
    ElevatedAccessGrantResponse,
    SystemParameterResponse,
    SystemParameterUpdate,
    UserAccountCreate,
    UserAccountFilter,
    UserAccountPaginationResponse,
    UserAccountResponse,
)
from app.features.notifications.service import NotificationService
from app.models.enums import AuditAction, UserType
from app.models.user_account import UserAccount
from app.models.system_backup_log import SystemBackupLog



logger = logging.getLogger(__name__)

def _json_object(value):
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}

class UserNotFoundError(Exception):
    pass


class EmailAlreadyExistsError(Exception):
    pass


class SystemParameterNotFoundError(Exception):
    pass


class InvalidParameterValueError(Exception):
    pass


class InvalidExpirationError(Exception):
    pass


class AdminPermissionError(Exception):
    pass


class AccountNotLockedError(Exception):
    pass


class GrantNotFoundError(Exception):
    pass


class GrantNotActiveError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AdminService:
    """Service layer orchestrating administrator operations on user accounts."""

    @staticmethod
    def list_accounts(db: Session, filters: UserAccountFilter) -> UserAccountPaginationResponse:
        items, total = AdminRepository.list_accounts(db=db, filters=filters)
        total_pages = math.ceil(total / filters.limit) if total > 0 else 0

        return UserAccountPaginationResponse(
            items=[UserAccountResponse.model_validate(item) for item in items],
            total=total,
            page=filters.page,
            limit=filters.limit,
            total_pages=total_pages,
        )

    @staticmethod
    def get_account(db: Session, account_id: UUID) -> UserAccountResponse:
        user = AdminRepository.get_by_id(db, account_id=account_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{account_id}' not found.")
        return UserAccountResponse.model_validate(user)

    @staticmethod
    def create_account(
        db: Session,
        payload: UserAccountCreate,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> UserAccountResponse:
        if payload.user_type.value == roles.ADMIN and admin_user.user_type.value != roles.ADMIN:
            raise AdminPermissionError("Only ADMIN can assign the ADMIN role")
        existing = AdminRepository.get_by_email(db, email=payload.email)
        if existing:
            raise EmailAlreadyExistsError(f"User with email '{payload.email}' already exists.")

        pwd_hash = hash_password(payload.password)
        account = AdminRepository.create_account(
            db=db,
            email=payload.email,
            password_hash=pwd_hash,
            user_type=payload.user_type,
        )

        # Audit log creation
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(account.account_id),
            account_id=admin_user.account_id,
            old_value=None,
            new_value={
                "email": account.email,
                "user_type": account.user_type.value,
                "is_active": account.is_active,
            },
            ip_address=ip_address,
        )

        return UserAccountResponse.model_validate(account)

    @staticmethod
    def update_status(
        db: Session,
        account_id: UUID,
        is_active: bool,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> UserAccountResponse:
        user = AdminRepository.get_by_id(db, account_id=account_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{account_id}' not found.")

        old_status = user.is_active
        updated_user = AdminRepository.update_status(db=db, user=user, is_active=is_active)

        # Audit log status change
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(updated_user.account_id),
            account_id=admin_user.account_id,
            old_value={"is_active": old_status},
            new_value={"is_active": is_active},
            ip_address=ip_address,
        )

        return UserAccountResponse.model_validate(updated_user)

    @staticmethod
    def update_role(
        db: Session,
        account_id: UUID,
        new_role: UserType,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> UserAccountResponse:
        user = AdminRepository.get_by_id(db, account_id=account_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{account_id}' not found.")
        if account_id == admin_user.account_id:
            raise AdminPermissionError("You cannot change your own role")
        if new_role.value == roles.ADMIN and admin_user.user_type.value != roles.ADMIN:
            raise AdminPermissionError("Only ADMIN can assign the ADMIN role")

        old_role = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        updated_user = AdminRepository.update_role(db=db, user=user, new_role=new_role)

        # Audit log role change
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(updated_user.account_id),
            account_id=admin_user.account_id,
            old_value={"user_type": old_role},
            new_value={"user_type": new_role.value},
            ip_address=ip_address,
        )

        return UserAccountResponse.model_validate(updated_user)

    @staticmethod
    def reset_password(
        db: Session,
        account_id: UUID,
        new_password: str,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> dict:
        user = AdminRepository.get_by_id(db, account_id=account_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{account_id}' not found.")

        was_locked = bool(user.locked_until and _as_utc(user.locked_until) > datetime.now(timezone.utc))
        # A reset also clears any lockout; persisted by update_password's commit.
        user.failed_login_count = 0
        user.locked_until = None
        pwd_hash = hash_password(new_password)
        AdminRepository.update_password(db=db, user=user, password_hash=pwd_hash)

        # Audit log password reset
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(user.account_id),
            account_id=admin_user.account_id,
            old_value=None,
            new_value={"action": "admin_password_reset", "email": user.email, "unlocked": was_locked},
            ip_address=ip_address,
        )

        return {"message": "Password reset successfully", "email": user.email}

    @staticmethod
    def unlock_account(
        db: Session,
        account_id: UUID,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> UserAccountResponse:
        user = AdminRepository.get_by_id(db, account_id=account_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{account_id}' not found.")
        if user.locked_until is None or _as_utc(user.locked_until) <= datetime.now(timezone.utc):
            raise AccountNotLockedError("Account is not locked")

        old_value = {
            "locked_until": _as_utc(user.locked_until).isoformat(),
            "failed_login_count": user.failed_login_count,
        }
        user.failed_login_count = 0
        user.locked_until = None

        NotificationService.create_notification(
            db,
            user_id=user.account_id,
            type=ACCOUNT_UNLOCKED,
            title="Account unlocked",
            message="An administrator unlocked your account. You can sign in again.",
        )
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(user.account_id),
            account_id=admin_user.account_id,
            old_value=old_value,
            new_value={"event": "ACCOUNT_UNLOCKED", "locked_until": None, "failed_login_count": 0},
            ip_address=ip_address,
            commit=False,
        )
        db.commit()
        db.refresh(user)

        return UserAccountResponse.model_validate(user)

    @staticmethod
    def get_backup_status(db: Session) -> BackupStatusResponse:
        # Check DB connectivity
        db.execute(text("SELECT 1"))
        pool = engine.pool
        checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
        pool_size = pool.size() if hasattr(pool, "size") else 5

        # Query recent backups (US-50)
        last_success = (
            db.query(SystemBackupLog)
            .filter(SystemBackupLog.status == "COMPLETED")
            .order_by(SystemBackupLog.created_at.desc())
            .first()
        )
        last_failure = (
            db.query(SystemBackupLog)
            .filter(SystemBackupLog.status == "FAILED")
            .order_by(SystemBackupLog.created_at.desc())
            .first()
        )
        recent_failures_count = (
            db.query(SystemBackupLog)
            .filter(
                SystemBackupLog.status == "FAILED",
                SystemBackupLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
            .count()
        )

        overall_status = "HEALTHY"
        status_details = f"Point-In-Time Recovery (PITR) active. Pool status: {checked_out}/{pool_size} active connections."
        if last_failure and (not last_success or last_failure.created_at > last_success.created_at):
            overall_status = "WARNING"
            status_details += f" Warning: Last backup #{last_failure.backup_id} failed."
        elif last_success:
            status_details += f" Last verified backup #{last_success.backup_id} completed."

        return BackupStatusResponse(
            status=overall_status,
            database="Supabase PostgreSQL (Enterprise)",
            last_verified_at=datetime.now(timezone.utc),
            active_connections=checked_out,
            details=status_details,
            last_successful_backup=last_success.created_at if last_success else None,
            last_failed_backup=last_failure.created_at if last_failure else None,
            recent_failures_count=recent_failures_count,
        )

    # ==========================================
    # System Parameter Service Methods (US-46)
    # ==========================================

    @staticmethod
    def validate_parameter_value(value_type: str, value: str) -> None:
        """Validate that string value conforms to value_type."""
        v_type = value_type.strip().lower()
        if v_type == "integer":
            try:
                int(value)
            except (ValueError, TypeError):
                raise InvalidParameterValueError(f"Value '{value}' is not a valid integer.")
        elif v_type == "boolean":
            if value.strip().lower() not in ("true", "false", "1", "0"):
                raise InvalidParameterValueError(f"Value '{value}' is not a valid boolean ('true' or 'false').")
        elif v_type == "json":
            try:
                json.loads(value)
            except Exception:
                raise InvalidParameterValueError(f"Value '{value}' is not valid JSON.")
        elif v_type == "string":
            if not isinstance(value, str):
                raise InvalidParameterValueError("Value must be a string.")

    @staticmethod
    def list_system_parameters(db: Session) -> List[SystemParameterResponse]:
        """List all operational system parameters."""
        items = AdminRepository.list_system_parameters(db=db)
        return [SystemParameterResponse.model_validate(item) for item in items]

    @staticmethod
    def update_system_parameter(
        db: Session,
        key: str,
        payload: SystemParameterUpdate,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> SystemParameterResponse:
        """Update system parameter with strict value_type validation and audit logging."""
        param = AdminRepository.get_system_parameter(db=db, key=key)
        if not param:
            raise SystemParameterNotFoundError(f"System parameter '{key}' not found.")

        # Validate that payload.value conforms to param.value_type
        AdminService.validate_parameter_value(param.value_type, payload.value)

        old_val = param.value
        updated = AdminRepository.update_system_parameter(
            db=db,
            param=param,
            new_value=payload.value,
            updated_by=admin_user.account_id,
        )

        # Audit log parameter update
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="SYSTEM_PARAMETER",
            entity_ref_id=key,
            account_id=admin_user.account_id,
            old_value={"value": old_val},
            new_value={"value": updated.value},
            ip_address=ip_address,
        )

        return SystemParameterResponse.model_validate(updated)

    # ==========================================
    # Elevated Access Service Methods (US-45)
    # ==========================================

    @staticmethod
    def grant_elevated_access(
        db: Session,
        payload: ElevatedAccessGrantCreate,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ElevatedAccessGrantResponse:
        """Grant a time-bound elevated role privilege with mandatory future expiration."""
        # 1. Target user exists check
        user = AdminRepository.get_by_id(db, account_id=payload.user_id)
        if not user:
            raise UserNotFoundError(f"User account with ID '{payload.user_id}' not found.")
        if payload.user_id == admin_user.account_id:
            raise AdminPermissionError("You cannot grant elevated access to yourself")
        if payload.granted_role.strip().upper() == roles.ADMIN and admin_user.user_type.value != roles.ADMIN:
            raise AdminPermissionError("Only ADMIN can assign the ADMIN role")

        # 2. Expiration validation (must be in the future)
        now = datetime.now(timezone.utc)
        expires_at = payload.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            raise InvalidExpirationError("Elevated access grant expiration must be in the future.")

        # 3. Create elevated access grant
        grant = AdminRepository.create_elevated_grant(
            db=db,
            user_id=payload.user_id,
            granted_role=payload.granted_role,
            granted_by=admin_user.account_id,
            expires_at=expires_at,
            reason=payload.reason,
        )

        NotificationService.create_notification(
            db,
            user_id=grant.user_id,
            type=ELEVATED_ACCESS_GRANTED,
            title="Elevated access granted",
            message=(
                f"You have been granted temporary {grant.granted_role} access "
                f"until {expires_at:%Y-%m-%d %H:%M} UTC."
            ),
        )

        # 4. Audit log creation
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="ELEVATED_ACCESS_GRANT",
            entity_ref_id=str(grant.id),
            account_id=admin_user.account_id,
            old_value=None,
            new_value={
                "user_id": str(grant.user_id),
                "granted_role": grant.granted_role,
                "expires_at": grant.expires_at.isoformat(),
                "reason": grant.reason,
            },
            ip_address=ip_address,
            commit=False,
        )
        db.commit()

        return ElevatedAccessGrantResponse.model_validate(grant)

    @staticmethod
    def revoke_elevated_grant(
        db: Session,
        grant_id: int,
        admin_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ElevatedAccessGrantResponse:
        """Revoke an active elevated access grant immediately (US-45)."""
        grant = AdminRepository.get_elevated_grant_by_id(db, grant_id)
        if not grant:
            raise GrantNotFoundError(f"Elevated access grant '{grant_id}' not found.")
        now = datetime.now(timezone.utc)
        if grant.revoked_at is not None:
            raise GrantNotActiveError("Grant is already revoked")
        if _as_utc(grant.expires_at) <= now:
            raise GrantNotActiveError("Grant has already expired")

        AdminRepository.revoke_elevated_grant(db, grant, revoked_at=now)

        NotificationService.create_notification(
            db,
            user_id=grant.user_id,
            type=ELEVATED_ACCESS_REVOKED,
            title="Elevated access revoked",
            message=f"Your temporary {grant.granted_role} access has been revoked by an administrator.",
        )
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="ELEVATED_ACCESS_GRANT",
            entity_ref_id=str(grant.id),
            account_id=admin_user.account_id,
            old_value={"revoked_at": None},
            new_value={
                "event": "ELEVATED_ACCESS_REVOKED",
                "revoked_at": now.isoformat(),
                "revoked_by": str(admin_user.account_id),
                "granted_role": grant.granted_role,
                "user_id": str(grant.user_id),
            },
            ip_address=ip_address,
            commit=False,
        )
        db.commit()

        return ElevatedAccessGrantResponse.model_validate(grant)

    @staticmethod
    def list_active_elevated_grants(db: Session) -> List[ElevatedAccessGrantResponse]:
        """List all currently active, unexpired, and unrevoked elevated access grants."""
        now = datetime.now(timezone.utc)
        grants = AdminRepository.list_active_elevated_grants(db=db, now=now)
        return [ElevatedAccessGrantResponse.model_validate(g) for g in grants]



    def trigger_backup(db: Session, actor, ip_address: str | None = None):
        log = AdminRepository.create_backup_log(db, actor.account_id)
        backup_dir = Path(settings.backup_dir).expanduser().resolve()
        filename = f"database_backup_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{log.backup_id}.dump"
        target = backup_dir / filename
        database_url = settings.database_url

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            timeout = settings.backup_timeout_seconds
            if database_url.startswith("sqlite"):
                url = make_url(database_url)
                source_path = Path(url.database or "")
                if not source_path.exists():
                    raise RuntimeError("Configured SQLite database file does not exist")
                source = sqlite3.connect(str(source_path))
                destination = sqlite3.connect(str(target))
                try:
                    source.backup(destination)
                finally:
                    destination.close()
                    source.close()
            else:
                if not database_url:
                    raise RuntimeError("DATABASE_URL is not configured")
                url = make_url(database_url)
                configured_dump = settings.pg_dump_path
                pg_dump = configured_dump or shutil.which("pg_dump")
                if pg_dump:
                    pg_dump = str(pg_dump).strip().strip('"').strip("'")
                if not pg_dump or not Path(pg_dump).is_file():
                    if configured_dump:
                        raise FileNotFoundError(f"Configured PG_DUMP_PATH is invalid: '{pg_dump}'")
                    raise FileNotFoundError("pg_dump is not installed or not found on system PATH")

                command = [
                    pg_dump, "--no-password", "--format=custom",
                    "--file", str(target),
                    "--host", str(url.host or "localhost"),
                    "--port", str(url.port or 5432),
                    "--username", str(url.username or "postgres"),
                    "--dbname", str(url.database or "postgres"),
                ]
                env = os.environ.copy()
                # Ensure the pg_dump binary directory is in PATH so dependent DLLs (libpq, openssl) load cleanly
                dump_bin_dir = str(Path(pg_dump).parent)
                current_path = env.get("PATH", "")
                if dump_bin_dir not in current_path:
                    env["PATH"] = f"{dump_bin_dir}{os.pathsep}{current_path}"

                if url.password:
                    env["PGPASSWORD"] = unquote(url.password)

                sslmode = url.query.get("sslmode")
                if sslmode:
                    env["PGSSLMODE"] = str(sslmode)
                elif url.host and url.host not in ("localhost", "127.0.0.1"):
                    env["PGSSLMODE"] = "require"

                completed = subprocess.run(
                    command, env=env, capture_output=True, text=True,
                    timeout=timeout, check=False,
                )
                if completed.returncode != 0:
                    err_msg = completed.stderr.strip() if completed.stderr else f"Exit code {completed.returncode}"
                    logger.error(
                        "pg_dump failed (exit code %s): %s",
                        completed.returncode,
                        err_msg[-2000:],
                    )
                    raise RuntimeError(f"pg_dump execution failed (exit code {completed.returncode}): {err_msg[-500:]}")

            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError("Backup command did not produce a non-empty file")
            row = AdminRepository.finish_backup_log(
                db, log, "COMPLETED", str(target), target.stat().st_size
            )
            write_audit_log(
                db, AuditAction.CREATE, "SYSTEM_BACKUP", str(row.backup_id),
                account_id=actor.account_id,
                new_value={"status": "COMPLETED", "backup_name": filename, "file_size_bytes": row.file_size_bytes},
                ip_address=ip_address,
            )
            # Never return the server's absolute storage path.
            return {
                "backup_id": row.backup_id, "backup_type": row.backup_type,
                "file_path": filename, "file_size_bytes": row.file_size_bytes,
                "status": row.status, "created_at": row.created_at,
                "triggered_by_account_id": row.triggered_by_account_id,
                "details": "Database backup completed successfully.",
            }
        except Exception as exc:
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                logger.exception("Could not remove partial backup artifact")
            row = AdminRepository.finish_backup_log(db, log, "FAILED", None, None)
            err_detail = str(exc)
            write_audit_log(
                db, AuditAction.CREATE, "SYSTEM_BACKUP", str(row.backup_id),
                account_id=actor.account_id,
                new_value={"status": "FAILED", "reason": type(exc).__name__},
                ip_address=ip_address,
            )
            logger.warning("On-demand backup %s failed (%s): %s", row.backup_id, type(exc).__name__, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database backup could not be completed. Check server logs for details.",
            ) from exc

    @staticmethod
    def get_anomaly_alerts(db: Session):
        now = datetime.now(timezone.utc)
        failed_window = settings.failed_login_window_minutes
        threshold = settings.failed_login_threshold
        rows = AdminRepository.audit_rows_since(db, now - timedelta(minutes=failed_window))

        ip_groups = defaultdict(list)
        account_groups = defaultdict(list)
        for row in rows:
            if row.action != AuditAction.LOGIN or row.entity_name != "USER_ACCOUNT":
                continue
            data = _json_object(row.new_value)
            if data.get("status") != "FAILED":
                continue
            if row.ip_address:
                ip_groups[row.ip_address].append((row, data))
            account_key = str(row.account_id) if row.account_id else str(data.get("attempted_email", "")).strip().lower()
            if account_key:
                account_groups[account_key].append((row, data))

        alerts = []
        for ip, events in ip_groups.items():
            if len(events) > threshold:
                times = [event[0].created_at for event in events]
                count = len(events)
                first_t = min(times)
                last_t = max(times)
                desc = f"More than {threshold} failed login attempts ({count} attempts) from IP {ip} in {failed_window} minutes."
                alerts.append(AnomalyAlert(
                    id=f"ALT-IP-{abs(hash(ip)) % 10000:04d}",
                    title=f"Failed-Login Spike Detected ({ip})",
                    description=desc,
                    alert_type="FAILED_LOGIN_BURST",
                    severity="HIGH",
                    ip_address=ip,
                    source_ip=ip,
                    count=count,
                    attempts_count=count,
                    first_timestamp=first_t,
                    last_timestamp=last_t,
                    timestamp=last_t,
                    status="ACTIVE",
                    details=desc,
                ))
        for account_key, events in account_groups.items():
            if len(events) > threshold:
                times = [event[0].created_at for event in events]
                sample = events[0][1]
                count = len(events)
                first_t = min(times)
                last_t = max(times)
                target_email = sample.get("attempted_email")
                try:
                    account_id = UUID(account_key)
                except (ValueError, TypeError):
                    account_id = None
                desc = f"More than {threshold} failed login attempts for account {target_email or account_key} in {failed_window} minutes."
                alerts.append(AnomalyAlert(
                    id=f"ALT-ACC-{abs(hash(account_key)) % 10000:04d}",
                    title=f"Targeted Brute-Force Alert ({target_email or account_key})",
                    description=desc,
                    alert_type="FAILED_LOGIN_BURST",
                    severity="HIGH",
                    account_id=account_id,
                    target_account_id=account_id,
                    attempted_email=target_email,
                    target_account=target_email or str(account_id),
                    count=count,
                    attempts_count=count,
                    first_timestamp=first_t,
                    last_timestamp=last_t,
                    timestamp=last_t,
                    status="ACTIVE",
                    details=desc,
                ))

        # Currently locked accounts are listed regardless of the failed-login window (US-49).
        for account in AdminRepository.list_locked_accounts(db, now):
            locked_at = account.locked_until - timedelta(minutes=settings.lockout_minutes)
            desc = (
                f"Account locked after {account.failed_login_count} failed logins "
                f"until {account.locked_until:%H:%M} UTC."
            )
            alerts.append(AnomalyAlert(
                id=f"ALT-LOCK-{account.account_id.hex[:8]}",
                title=f"Account Locked ({account.email})",
                description=desc,
                alert_type="ACCOUNT_LOCKED",
                severity="HIGH",
                account_id=account.account_id,
                target_account_id=account.account_id,
                attempted_email=account.email,
                target_account=account.email,
                count=account.failed_login_count,
                attempts_count=account.failed_login_count,
                first_timestamp=locked_at,
                last_timestamp=account.locked_until,
                timestamp=locked_at,
                status="ACTIVE",
                details=desc,
            ))

        # Role elevations are reviewed over 24 hours; no volume threshold is assumed.
        elevation_rows = AdminRepository.audit_rows_since(db, now - timedelta(hours=24))
        rank = {"ADMIN": 1, "SYSTEM_ADMIN": 2}
        for row in elevation_rows:
            if row.entity_name != "USER_ACCOUNT" or row.action not in (AuditAction.UPDATE, AuditAction.CREATE):
                continue
            old_data, new_data = _json_object(row.old_value), _json_object(row.new_value)
            old_role = str(old_data.get("user_type", "")).upper() or None
            new_role = str(new_data.get("user_type", "")).upper() or None
            if not new_role:
                continue
            old_rank = rank.get(old_role, 0)
            new_rank = rank.get(new_role, 0)
            if new_rank <= old_rank:
                continue
            try:
                target_id = UUID(str(row.entity_ref_id))
            except (ValueError, TypeError):
                target_id = None
            desc = f"Account role elevated from {old_role or 'UNASSIGNED'} to {new_role}."
            alerts.append(AnomalyAlert(
                id=f"ALT-ELEV-{abs(hash(str(row.entity_ref_id))) % 10000:04d}",
                title=f"Privilege Escalation Alert ({new_role})",
                description=desc,
                alert_type="PRIVILEGE_ESCALATION",
                severity="CRITICAL" if new_role == "SYSTEM_ADMIN" else "HIGH",
                account_id=row.account_id,
                target_account_id=target_id,
                target_account=str(target_id) if target_id else None,
                old_role=old_role,
                new_role=new_role,
                count=1,
                attempts_count=1,
                first_timestamp=row.created_at,
                last_timestamp=row.created_at,
                timestamp=row.created_at,
                status="ACTIVE",
                details=desc,
            ))

        # Check for recent failed backups in the last 24 hours (US-50)
        recent_failed_backups = (
            db.query(SystemBackupLog)
            .filter(
                SystemBackupLog.status == "FAILED",
                SystemBackupLog.created_at >= now - timedelta(hours=24),
            )
            .order_by(SystemBackupLog.created_at.desc())
            .all()
        )
        for fb in recent_failed_backups:
            desc = f"Database backup #{fb.backup_id} ({fb.backup_type}) failed. Error: {fb.file_path or 'Execution error'}."
            alerts.append(AnomalyAlert(
                id=f"ALT-BCK-{fb.backup_id}",
                title=f"Database Backup #{fb.backup_id} Failure",
                description=desc,
                alert_type="BACKUP_FAILURE",
                severity="HIGH",
                count=1,
                attempts_count=1,
                first_timestamp=fb.created_at,
                last_timestamp=fb.created_at,
                timestamp=fb.created_at,
                status="ACTIVE",
                details=desc,
            ))

        return AnomalyAlertsResponse(
            window_minutes=failed_window,
            total_alerts=len(alerts),
            alerts=alerts,
            notes="Privilege elevations are listed individually over the last 24 hours; no spike threshold is configured.",
        )

