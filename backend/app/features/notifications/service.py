from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationService:
    """
    Centralized notification operations (US-19, S2-BE-4).

    NOTE: The service flushes and refreshes but DOES NOT commit transactions.
    Commits are owned by the caller (router or invoking domain service)
    so notifications join the atomic transaction of the caller.
    """

    @staticmethod
    def create_notification(
        db: Session,
        user_id: UUID,
        type: str,
        title: str,
        message: str,
        link: Optional[str] = None,
    ) -> Notification:
        """
        Creates and flushes a new notification record without committing.
        Safe for invocation by other domain services within their transactions.
        """
        notification = Notification(
            account_id=user_id,
            type=type,
            title=title,
            message=message,
            link=link,
            is_read=False,
        )
        db.add(notification)
        db.flush()
        db.refresh(notification)
        return notification

    @staticmethod
    def list_my_notifications(
        db: Session,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> Tuple[List[Notification], int]:
        """
        Retrieves paginated notifications for the given user, ordered newest first.
        Returns a tuple of (items, total_count).
        """
        query = db.query(Notification).filter(Notification.account_id == user_id)

        if unread_only:
            query = query.filter(Notification.is_read.is_(False))

        total = query.with_entities(func.count(Notification.id)).scalar() or 0

        offset = (page - 1) * page_size
        items = (
            query.order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total

    @staticmethod
    def get_unread_count(db: Session, user_id: UUID) -> int:
        """
        Returns count of unread notifications for the user.
        Uses compound index (account_id, is_read).
        """
        count = (
            db.query(func.count(Notification.id))
            .filter(
                Notification.account_id == user_id,
                Notification.is_read.is_(False),
            )
            .scalar()
        )
        return count or 0

    @staticmethod
    def mark_as_read(
        db: Session,
        user_id: UUID,
        notification_id: UUID,
    ) -> Optional[Notification]:
        """
        Marks a specific notification as read if it belongs to the user.
        Returns None if not found or owned by another user.
        """
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.account_id == user_id,
            )
            .first()
        )

        if not notification:
            return None

        if not notification.is_read:
            notification.is_read = True
            db.flush()
            db.refresh(notification)

        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: UUID) -> int:
        """
        Bulk updates all unread notifications for a user to is_read = True.
        Returns the number of rows updated.
        """
        stmt = (
            update(Notification)
            .where(
                Notification.account_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
            .execution_options(synchronize_session=False)
        )
        result = db.execute(stmt)
        db.flush()
        return result.rowcount or 0

