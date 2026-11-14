from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket, TicketActivity
from app.models.user_account import UserAccount
from app.models.notification import Notification
from app.models.enums import UserType


class SupportTicketRepository:
    @staticmethod
    def get_by_id(db: Session, ticket_id: int) -> Optional[SupportTicket]:
        return db.get(SupportTicket, ticket_id)

    @staticmethod
    def create_activity(
        db: Session,
        ticket_id: int,
        activity_type: str,
        details: Optional[str] = None,
        actor_account_id: Optional[UUID] = None,
    ) -> TicketActivity:
        activity = TicketActivity(
            ticket_id=ticket_id,
            activity_type=activity_type,
            details=details,
            actor_account_id=actor_account_id,
        )
        db.add(activity)
        return activity

    @staticmethod
    def get_eligible_system_admins(db: Session) -> List[UserAccount]:
        """
        Fetch all active System Administrator accounts.
        Strictly restricted to actual SYSTEM_ADMIN users per official role definitions.
        ADMIN users are not assumed equivalent to SYSTEM_ADMIN without documented evidence.
        """
        sys_admin_roles = [
            UserType.SYSTEM_ADMIN,
            "SYSTEM_ADMIN",
        ]
        stmt = select(UserAccount).where(
            UserAccount.is_active.is_(True),
            UserAccount.user_type.in_(sys_admin_roles),
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_notification(
        db: Session,
        account_id: UUID,
        type_: str,
        title: str,
        message: str,
    ) -> Notification:
        notification = Notification(
            account_id=account_id,
            type=type_,
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        return notification

