from typing import Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.notification import Notification


def notify(
    db: Session,
    recipient_id: UUID,
    type: str,
    title: str,
    message: str,
    related_entity_id: Optional[Any] = None,
) -> Notification:
    """
    Send a notification to an employee/user account complying with Epic 6 (US-19).
    Persists notification record into database for the recipient user account.
    """
    notification = Notification(
        account_id=recipient_id,
        type=str(type),
        title=str(title),
        message=str(message),
        is_read=False,
    )
    db.add(notification)
    return notification

