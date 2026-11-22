from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.notification_types import SECURITY_ALERT
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, UserType
from app.models.notification import Notification
from app.models.user_account import UserAccount


PASSWORD = "CorrectPass123!"


# ==============================================================================
# Shared fixtures: one in-memory SQLite DB for the module, wired into app.main
# ==============================================================================

@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield factory
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    engine.dispose()


@pytest.fixture(scope="module")
def client(session_factory):
    return TestClient(app)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# Helpers
# ==============================================================================

def make_account(db, user_type: UserType = UserType.EMPLOYEE) -> UserAccount:
    account = UserAccount(
        account_id=uuid4(),
        email=f"{user_type.value.lower()}-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password(PASSWORD),
        user_type=user_type,
        is_active=True,
    )
    db.add(account)
    db.commit()
    return account


def login(client, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ==============================================================================
# Account lockout (US-48, US-49)
# ==============================================================================

def test_lockout_after_threshold_returns_423(client, db):
    admin = make_account(db, UserType.SYSTEM_ADMIN)
    account = make_account(db)
    threshold = settings.failed_login_threshold

    for attempt in range(1, threshold + 1):
        res = login(client, account.email, "WrongPass!")
        assert res.status_code == 401, attempt

    db.refresh(account)
    assert account.failed_login_count == threshold
    assert account.locked_until is not None
    locked_until = as_utc(account.locked_until)
    assert locked_until > datetime.now(timezone.utc)

    alert = (
        db.query(Notification)
        .filter(Notification.account_id == admin.account_id, Notification.type == SECURITY_ALERT)
        .one()
    )
    assert account.email in alert.message

    res = login(client, account.email, PASSWORD)
    assert res.status_code == 423
    assert res.json()["detail"] == (
        f"Account locked. Try again after {locked_until:%H:%M} UTC or contact an administrator."
    )

    locked_rows = [
        row
        for row in db.query(AuditLog).filter(
            AuditLog.action == AuditAction.LOGIN,
            AuditLog.account_id == account.account_id,
        )
        if '"LOCKED"' in (row.new_value or "")
    ]
    assert len(locked_rows) == 1

    # An expired lock no longer blocks the correct password.
    account.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    res = login(client, account.email, PASSWORD)
    assert res.status_code == 200
    db.refresh(account)
    assert account.failed_login_count == 0
    assert account.locked_until is None


def test_successful_login_resets_counter(client, db):
    account = make_account(db)

    for _ in range(3):
        assert login(client, account.email, "WrongPass!").status_code == 401
    db.refresh(account)
    assert account.failed_login_count == 3

    res = login(client, account.email, PASSWORD)
    assert res.status_code == 200
    db.refresh(account)
    assert account.failed_login_count == 0
    assert account.locked_until is None
