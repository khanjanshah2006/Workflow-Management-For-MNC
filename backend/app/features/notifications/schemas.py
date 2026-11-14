from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    """Output representation of a single notification."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    type: str
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime


class PaginatedNotifications(BaseModel):
    """Paginated list of user notifications."""
    items: List[NotificationOut]
    total: int = Field(..., ge=0, description="Total count of matching notifications")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=100, description="Max items per page")


class UnreadCountOut(BaseModel):
    """Response containing total unread notifications count."""
    count: int = Field(..., ge=0, description="Number of unread notifications")


class MarkAllReadOut(BaseModel):
    """Result of marking all notifications as read."""
    updated: int = Field(..., ge=0, description="Number of notifications marked as read")

