from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.features.admin.schemas import UserAccountFilter
from app.models.enums import UserType
from app.models.user_account import UserAccount
from app.models.system_parameter import SystemParameter
from app.models.elevated_access_grant import ElevatedAccessGrant


class AdminRepository:
    """Repository layer for database access to user accounts by system administrators."""

    @staticmethod
    def list_accounts(db: Session, filters: UserAccountFilter) -> Tuple[List[UserAccount], int]:
        query = db.query(UserAccount)

        if filters.search:
            query = query.filter(UserAccount.email.ilike(f"%{filters.search.strip()}%"))

        if filters.user_type:
            query = query.filter(UserAccount.user_type == filters.user_type)

        if filters.is_active is not None:
            query = query.filter(UserAccount.is_active == filters.is_active)

        total = query.count()

        offset = (filters.page - 1) * filters.limit
        items = (
            query.order_by(UserAccount.created_at.desc())
            .offset(offset)
            .limit(filters.limit)
            .all()
        )

        return items, total

    @staticmethod
    def get_by_id(db: Session, account_id: UUID) -> Optional[UserAccount]:
        return db.query(UserAccount).filter(UserAccount.account_id == account_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[UserAccount]:
        return db.query(UserAccount).filter(UserAccount.email.ilike(email.strip())).first()

    @staticmethod
    def create_account(
        db: Session, email: str, password_hash: str, user_type: UserType
    ) -> UserAccount:
        account = UserAccount(
            email=email.strip().lower(),
            password_hash=password_hash,
            user_type=user_type,
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def update_status(db: Session, user: UserAccount, is_active: bool) -> UserAccount:
        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_role(db: Session, user: UserAccount, new_role: UserType) -> UserAccount:
        user.user_type = new_role
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_password(db: Session, user: UserAccount, password_hash: str) -> UserAccount:
        user.password_hash = password_hash
        db.commit()
        db.refresh(user)
        return user

    # ==========================================
    # System Parameter Repository Methods (US-46)
    # ==========================================

    @staticmethod
    def list_system_parameters(db: Session) -> List[SystemParameter]:
        """Fetch all operational system parameters ordered by key."""
        return db.query(SystemParameter).order_by(SystemParameter.key.asc()).all()

    @staticmethod
    def get_system_parameter(db: Session, key: str) -> Optional[SystemParameter]:
        """Fetch a single system parameter by unique key."""
        return db.query(SystemParameter).filter(SystemParameter.key == key.strip()).first()

    @staticmethod
    def update_system_parameter(
        db: Session,
        param: SystemParameter,
        new_value: str,
        updated_by: UUID,
    ) -> SystemParameter:
        """Update system parameter value and modifier."""
        param.value = new_value
        param.updated_by = updated_by
        db.commit()
        db.refresh(param)
        return param

    # ==========================================
    # Elevated Access Repository Methods (US-45)
    # ==========================================

    @staticmethod
    def create_elevated_grant(
        db: Session,
        user_id: UUID,
        granted_role: str,
        granted_by: UUID,
        expires_at: datetime,
        reason: str,
    ) -> ElevatedAccessGrant:
        """Create a new time-bound elevated access grant."""
        grant = ElevatedAccessGrant(
            user_id=user_id,
            granted_role=granted_role.strip().upper(),
            granted_by=granted_by,
            expires_at=expires_at,
            reason=reason.strip(),
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)
        return grant

    @staticmethod
    def list_active_elevated_grants(db: Session, now: datetime) -> List[ElevatedAccessGrant]:
        """Fetch all unexpired, unrevoked elevated access grants."""
        return (
            db.query(ElevatedAccessGrant)
            .filter(
                ElevatedAccessGrant.revoked_at.is_(None),
                ElevatedAccessGrant.expires_at > now,
            )
            .order_by(ElevatedAccessGrant.expires_at.asc())
            .all()
        )

    @staticmethod
    def get_elevated_grant_by_id(db: Session, grant_id: int) -> Optional[ElevatedAccessGrant]:
        """Fetch an elevated access grant by primary key."""
        return db.query(ElevatedAccessGrant).filter(ElevatedAccessGrant.id == grant_id).first()

    @staticmethod
    def revoke_elevated_grant(
        db: Session, grant: ElevatedAccessGrant, revoked_at: datetime
    ) -> ElevatedAccessGrant:
        """Mark an elevated grant as revoked immediately."""
        grant.revoked_at = revoked_at
        db.commit()
        db.refresh(grant)
        return grant

