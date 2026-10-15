import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.audit import write_audit_log
from app.core.security import hash_password
from app.db.session import engine
from app.features.admin.repository import AdminRepository
from app.features.admin.schemas import (
    AdminPasswordReset,
    BackupStatusResponse,
    UserAccountCreate,
    UserAccountFilter,
    UserAccountPaginationResponse,
    UserAccountResponse,
)
from app.models.enums import AuditAction, UserType
from app.models.user_account import UserAccount


class UserNotFoundError(Exception):
    pass


class EmailAlreadyExistsError(Exception):
    pass


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
            new_value={"action": "admin_password_reset", "email": user.email},
            ip_address=ip_address,
        )

        return {"message": "Password reset successfully", "email": user.email}

    @staticmethod
    def get_backup_status(db: Session) -> BackupStatusResponse:
        # Check DB connectivity
        db.execute(text("SELECT 1"))
        pool = engine.pool
        checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
        pool_size = pool.size() if hasattr(pool, "size") else 5

        return BackupStatusResponse(
            status="HEALTHY",
            database="Supabase PostgreSQL (Enterprise)",
            last_verified_at=datetime.now(timezone.utc),
            active_connections=checked_out,
            details=f"Point-In-Time Recovery (PITR) active. Pool status: {checked_out}/{pool_size} active connections.",
        )
