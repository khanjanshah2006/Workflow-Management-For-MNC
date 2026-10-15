from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.features.admin.schemas import UserAccountFilter
from app.models.enums import UserType
from app.models.user_account import UserAccount


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
