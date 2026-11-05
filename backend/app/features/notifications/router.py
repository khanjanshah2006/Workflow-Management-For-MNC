from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user_account import UserAccount
from app.features.notifications.schemas import (
    NotificationOut,
    PaginatedNotifications,
    UnreadCountOut,
    MarkAllReadOut,
)
from app.features.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get(
    "/my",
    response_model=PaginatedNotifications,
    status_code=status.HTTP_200_OK,
    summary="List notifications for authenticated user",
    description="Retrieve paginated notifications ordered by creation time descending with optional unread filter.",
)
def list_my_notifications(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedNotifications:
    items, total = NotificationService.list_my_notifications(
        db=db,
        user_id=current_user.account_id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )
    return PaginatedNotifications(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    status_code=status.HTTP_200_OK,
    summary="Get unread notification count",
    description="Returns the total number of unread notifications for the authenticated user.",
)
def get_unread_count(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnreadCountOut:
    count = NotificationService.get_unread_count(db=db, user_id=current_user.account_id)
    return UnreadCountOut(count=count)


@router.put(
    "/{id}/read",
    response_model=NotificationOut,
    status_code=status.HTTP_200_OK,
    summary="Mark single notification as read",
    description="Marks a notification as read. Returns 404 if not found or owned by another user.",
)
def mark_notification_as_read(
    id: UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    notification = NotificationService.mark_as_read(
        db=db,
        user_id=current_user.account_id,
        notification_id=id,
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    db.commit()
    return notification


@router.put(
    "/read-all",
    response_model=MarkAllReadOut,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Bulk marks all unread notifications for the authenticated user as read.",
)
def mark_all_notifications_as_read(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarkAllReadOut:
    updated = NotificationService.mark_all_as_read(
        db=db,
        user_id=current_user.account_id,
    )
    db.commit()
    return MarkAllReadOut(updated=updated)

