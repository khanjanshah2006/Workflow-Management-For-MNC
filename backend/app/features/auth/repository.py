from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    def update_last_login(db: Session, account: UserAccount) -> None:
        """Update last_login_at timestamp on existing entity without redundant query."""
        account.last_login_at = func.now()
        db.commit()
