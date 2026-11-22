from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.roles import PLATFORM_ADMINS
from app.models.user_account import UserAccount


class AuthRepository:
    """Repository handling SQL queries for user_account entity."""

    @staticmethod
    def get_by_email(db: Session, email: str) -> UserAccount | None:
        """Fetch user account by email address (case-insensitive)."""
        return (
            db.query(UserAccount)
            .filter(func.lower(UserAccount.email) == func.lower(email))
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, account_id: UUID) -> UserAccount | None:
        """Fetch user account by UUID primary key."""
        return db.query(UserAccount).filter(UserAccount.account_id == account_id).first()

    @staticmethod
    def list_active_platform_admins(db: Session) -> list[UserAccount]:
        """Active ADMIN and SYSTEM_ADMIN accounts (recipients of security alerts)."""
        return (
            db.query(UserAccount)
            .filter(UserAccount.user_type.in_(PLATFORM_ADMINS), UserAccount.is_active.is_(True))
            .all()
        )

    @staticmethod
    def update_last_login(db: Session, account: UserAccount) -> None:
        """Update last_login_at timestamp on existing entity without redundant query."""
        account.last_login_at = func.now()
        db.commit()
