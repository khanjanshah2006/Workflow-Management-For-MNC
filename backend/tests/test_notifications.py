import uuid
import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.enums import UserType
from app.models.user_account import UserAccount
from app.features.notifications.service import NotificationService
from app.features.notifications.router import (
    list_my_notifications,
    get_unread_count,
    mark_notification_as_read,
    mark_all_notifications_as_read,
)


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user_a(db_session):
    account = UserAccount(
        account_id=uuid.uuid4(),
        email="usera@example.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def user_b(db_session):
    account = UserAccount(
        account_id=uuid.uuid4(),
        email="userb@example.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def test_my_notifications_returns_only_my_notifications(db_session, user_a, user_b):
    """Test (a): /my returns only notifications belonging to the authenticated user."""
    # Create notifications for user_a
    notif_a1 = NotificationService.create_notification(
        db=db_session,
        user_id=user_a.account_id,
        type="task_assigned",
        title="Task 1 Assigned",
        message="You have been assigned to Task 1.",
    )
    notif_a2 = NotificationService.create_notification(
        db=db_session,
        user_id=user_a.account_id,
        type="leave_approved",
        title="Leave Approved",
        message="Your leave request was approved.",
    )

    # Create notification for user_b
    NotificationService.create_notification(
        db=db_session,
        user_id=user_b.account_id,
        type="task_assigned",
        title="User B Task",
        message="Task for user B.",
    )
    db_session.commit()

    # Query as user_a
    response = list_my_notifications(
        page=1,
        page_size=10,
        unread_only=False,
        current_user=user_a,
        db=db_session,
    )

    assert response.total == 2
    assert len(response.items) == 2
    returned_ids = {item.id for item in response.items}
    assert returned_ids == {notif_a1.id, notif_a2.id}
    for item in response.items:
        assert item.account_id == user_a.account_id


def test_marking_another_users_notification_returns_404(db_session, user_a, user_b):
    """Test (b): marking another user's notification returns 404 (never 403)."""
    notif_b = NotificationService.create_notification(
        db=db_session,
        user_id=user_b.account_id,
        type="system_alert",
        title="User B Alert",
        message="Private alert for User B.",
    )
    db_session.commit()

    # User A attempts to mark User B's notification as read
    with pytest.raises(HTTPException) as exc_info:
        mark_notification_as_read(
            id=notif_b.id,
            current_user=user_a,
            db=db_session,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Notification not found"


def test_unread_count_decrements_after_mark_read(db_session, user_a):
    """Test (c): unread-count decrements after marking a notification as read."""
    n1 = NotificationService.create_notification(
        db=db_session,
        user_id=user_a.account_id,
        type="mention",
        title="Mentioned",
        message="Someone mentioned you.",
    )
    NotificationService.create_notification(
        db=db_session,
        user_id=user_a.account_id,
        type="task_update",
        title="Task Updated",
        message="Task details changed.",
    )
    db_session.commit()

    initial_count = get_unread_count(current_user=user_a, db=db_session)
    assert initial_count.count == 2

    # Mark n1 as read
    mark_res = mark_notification_as_read(
        id=n1.id,
        current_user=user_a,
        db=db_session,
    )
    assert mark_res.is_read is True

    updated_count = get_unread_count(current_user=user_a, db=db_session)
    assert updated_count.count == 1


def test_read_all_sets_count_to_zero(db_session, user_a):
    """Test (d): read-all marks all notifications read and sets unread-count to 0."""
    for i in range(3):
        NotificationService.create_notification(
            db=db_session,
            user_id=user_a.account_id,
            type="announcement",
            title=f"Announcement {i}",
            message=f"Message {i}",
        )
    db_session.commit()

    initial_count = get_unread_count(current_user=user_a, db=db_session)
    assert initial_count.count == 3

    # Bulk mark all read
    res = mark_all_notifications_as_read(current_user=user_a, db=db_session)
    assert res.updated == 3

    final_count = get_unread_count(current_user=user_a, db=db_session)
    assert final_count.count == 0


def test_pagination_and_unread_only(db_session, user_a):
    """Test (e): pagination limits, page offsets, and unread_only filtering."""
    # Create 5 notifications: 3 unread, 2 read
    for i in range(5):
        NotificationService.create_notification(
            db=db_session,
            user_id=user_a.account_id,
            type="info",
            title=f"Notification {i}",
            message=f"Body {i}",
        )
    db_session.commit()

    # Mark 2 as read
    items_all, _ = NotificationService.list_my_notifications(
        db=db_session,
        user_id=user_a.account_id,
        page=1,
        page_size=10,
    )
    NotificationService.mark_as_read(db=db_session, user_id=user_a.account_id, notification_id=items_all[0].id)
    NotificationService.mark_as_read(db=db_session, user_id=user_a.account_id, notification_id=items_all[1].id)
    db_session.commit()

    # Pagination: page 1 with page_size=2
    p1 = list_my_notifications(
        page=1,
        page_size=2,
        unread_only=False,
        current_user=user_a,
        db=db_session,
    )
    assert p1.total == 5
    assert len(p1.items) == 2
    assert p1.page == 1
    assert p1.page_size == 2

    # Pagination: page 2 with page_size=2
    p2 = list_my_notifications(
        page=2,
        page_size=2,
        unread_only=False,
        current_user=user_a,
        db=db_session,
    )
    assert p2.total == 5
    assert len(p2.items) == 2
    assert p2.page == 2

    # Filter unread_only=True
    unread_res = list_my_notifications(
        page=1,
        page_size=10,
        unread_only=True,
        current_user=user_a,
        db=db_session,
    )
    assert unread_res.total == 3
    assert len(unread_res.items) == 3
    for notif in unread_res.items:
        assert notif.is_read is False


def test_create_notification_clean_import():
    """Test (f): create_notification can be cleanly imported from another feature module."""
    from app.features.notifications.service import NotificationService as NS

    assert hasattr(NS, "create_notification")
    assert callable(NS.create_notification)

