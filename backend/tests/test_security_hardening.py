from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.notification_types import (
    ACCOUNT_UNLOCKED,
    ELEVATED_ACCESS_GRANTED,
    ELEVATED_ACCESS_REVOKED,
    SECURITY_ALERT,
)
from app.core.security import create_access_token, create_mfa_pending_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.features.auth.rate_limit import LOGIN_RATE_LIMIT
from app.main import app
from app.models.audit_log import AuditLog
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.employee import Employee
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


def auth_headers(account: UserAccount) -> dict[str, str]:
    token = create_access_token(data={
        "sub": str(account.account_id),
        "email": account.email,
        "user_type": account.user_type.value,
    })
    return {"Authorization": f"Bearer {token}"}


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
        .filter(
            Notification.account_id == admin.account_id,
            Notification.type == SECURITY_ALERT,
            Notification.message.contains(account.email),
        )
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


def test_lockout_notifies_admins_and_appears_in_alerts(client, db):
    admin = make_account(db, UserType.ADMIN)
    system_admin = make_account(db, UserType.SYSTEM_ADMIN)
    inactive_admin = make_account(db, UserType.ADMIN)
    inactive_admin.is_active = False
    employee = make_account(db, UserType.EMPLOYEE)
    target = make_account(db)
    db.commit()

    for _ in range(settings.failed_login_threshold):
        assert login(client, target.email, "WrongPass!").status_code == 401

    def alerts_for(recipient: UserAccount) -> int:
        return (
            db.query(Notification)
            .filter(
                Notification.account_id == recipient.account_id,
                Notification.type == SECURITY_ALERT,
                Notification.message.contains(target.email),
            )
            .count()
        )

    assert alerts_for(admin) == 1
    assert alerts_for(system_admin) == 1
    assert alerts_for(inactive_admin) == 0
    assert alerts_for(employee) == 0

    def locked_alerts() -> list[dict]:
        res = client.get("/api/v1/admin/anomaly-alerts", headers=auth_headers(admin))
        assert res.status_code == 200
        return [
            alert
            for alert in res.json()["alerts"]
            if alert["alert_type"] == "ACCOUNT_LOCKED" and alert["target_account"] == target.email
        ]

    alerts = locked_alerts()
    assert len(alerts) == 1
    assert alerts[0]["id"] == f"ALT-LOCK-{target.account_id.hex[:8]}"
    assert alerts[0]["severity"] == "HIGH"
    assert alerts[0]["count"] == settings.failed_login_threshold

    db.refresh(target)
    target.locked_until = None
    db.commit()
    assert locked_alerts() == []


def test_unlock_and_reset_password_clear_lock(client, db):
    admin = make_account(db, UserType.ADMIN)
    system_admin = make_account(db, UserType.SYSTEM_ADMIN)
    employee = make_account(db, UserType.EMPLOYEE)
    target = make_account(db)

    def lock_target():
        for _ in range(settings.failed_login_threshold):
            assert login(client, target.email, "WrongPass!").status_code == 401
        db.expire_all()
        assert target.locked_until is not None

    lock_target()
    unlock_url = f"/api/v1/admin/users/{target.account_id}/unlock"

    assert client.post(unlock_url, headers=auth_headers(employee)).status_code == 403
    assert client.post(f"/api/v1/admin/users/{uuid4()}/unlock", headers=auth_headers(admin)).status_code == 404

    res = client.post(unlock_url, headers=auth_headers(admin))
    assert res.status_code == 200
    db.expire_all()
    assert target.failed_login_count == 0
    assert target.locked_until is None
    assert login(client, target.email, PASSWORD).status_code == 200

    unlock_rows = [
        row
        for row in db.query(AuditLog).filter(
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.entity_ref_id == str(target.account_id),
            AuditLog.account_id == admin.account_id,
        )
        if '"ACCOUNT_UNLOCKED"' in (row.new_value or "")
    ]
    assert len(unlock_rows) == 1
    assert (
        db.query(Notification)
        .filter(Notification.account_id == target.account_id, Notification.type == ACCOUNT_UNLOCKED)
        .count()
        == 1
    )

    res = client.post(unlock_url, headers=auth_headers(admin))
    assert res.status_code == 409
    assert res.json()["detail"] == "Account is not locked"

    # An admin password reset clears the lock too.
    lock_target()
    res = client.post(
        f"/api/v1/admin/users/{target.account_id}/reset-password",
        json={"new_password": "BrandNew123!"},
        headers=auth_headers(system_admin),
    )
    assert res.status_code == 200
    db.expire_all()
    assert target.failed_login_count == 0
    assert target.locked_until is None
    reset_row = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_ref_id == str(target.account_id),
            AuditLog.account_id == system_admin.account_id,
        )
        .one()
    )
    assert '"unlocked": true' in reset_row.new_value
    assert login(client, target.email, "BrandNew123!").status_code == 200


# ==============================================================================
# Elevated access revocation (US-45)
# ==============================================================================

def test_revoke_elevated_access_audited_and_effective(client, db):
    admin = make_account(db, UserType.ADMIN)
    grantee = make_account(db, UserType.EMPLOYEE)
    employee = Employee(
        account_id=grantee.account_id,
        emp_code=f"EMP-{uuid4().hex[:8]}",
        full_name="Grantee",
        email=grantee.email,
        designation="Engineer",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(employee)
    db.commit()
    workload_url = f"/api/v1/employees/{employee.emp_id}/workload"
    admin_headers = auth_headers(admin)
    grantee_headers = auth_headers(grantee)

    assert client.get(workload_url, headers=grantee_headers).status_code == 403
    res = client.post(
        "/api/v1/admin/elevated-access",
        json={
            "user_id": str(grantee.account_id),
            "granted_role": "PM",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "reason": "Covering for PM on leave",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201
    grant_id = res.json()["id"]
    assert client.get(workload_url, headers=grantee_headers).status_code == 200

    def notifications(type_: str) -> int:
        return (
            db.query(Notification)
            .filter(Notification.account_id == grantee.account_id, Notification.type == type_)
            .count()
        )

    assert notifications(ELEVATED_ACCESS_GRANTED) == 1

    revoke_url = f"/api/v1/admin/elevated-access/{grant_id}"
    assert client.delete(revoke_url, headers=grantee_headers).status_code == 403
    res = client.delete(revoke_url, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["revoked_at"] is not None

    assert client.get(workload_url, headers=grantee_headers).status_code == 403
    res = client.delete(revoke_url, headers=admin_headers)
    assert res.status_code == 409
    assert res.json()["detail"] == "Grant is already revoked"
    assert client.delete("/api/v1/admin/elevated-access/999999", headers=admin_headers).status_code == 404

    expired_owner = make_account(db, UserType.EMPLOYEE)
    expired = ElevatedAccessGrant(
        user_id=expired_owner.account_id,
        granted_role="PM",
        granted_by=admin.account_id,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        reason="Expired grant",
    )
    db.add(expired)
    db.commit()
    res = client.delete(f"/api/v1/admin/elevated-access/{expired.id}", headers=admin_headers)
    assert res.status_code == 409
    assert res.json()["detail"] == "Grant has already expired"

    active = client.get("/api/v1/admin/elevated-access/active", headers=admin_headers).json()
    assert grant_id not in [grant["id"] for grant in active]
    assert client.get("/api/v1/auth/me", headers=grantee_headers).json()["active_elevated_roles"] == []

    revoke_rows = [
        row
        for row in db.query(AuditLog).filter(
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.entity_name == "ELEVATED_ACCESS_GRANT",
            AuditLog.entity_ref_id == str(grant_id),
        )
        if '"ELEVATED_ACCESS_REVOKED"' in (row.new_value or "")
    ]
    assert len(revoke_rows) == 1
    assert revoke_rows[0].account_id == admin.account_id
    assert f'"revoked_by": "{admin.account_id}"' in revoke_rows[0].new_value
    assert notifications(ELEVATED_ACCESS_REVOKED) == 1


# ==============================================================================
# Admin MFA enforcement (US-31)
# ==============================================================================

def test_admin_without_mfa_gets_setup_required_when_enforced(client, db, monkeypatch):
    monkeypatch.setattr(settings, "enforce_admin_mfa", True)
    admin = make_account(db, UserType.ADMIN)
    system_admin = make_account(db, UserType.SYSTEM_ADMIN)
    employee = make_account(db, UserType.EMPLOYEE)

    setup_tokens = {}
    for account in (admin, system_admin):
        res = login(client, account.email, PASSWORD)
        assert res.status_code == 200
        body = res.json()
        assert body["mfa_setup_required"] is True
        assert body["mfa_required"] is False
        assert body["mfa_token"]
        assert body["access_token"] is None
        assert "refresh_token" not in res.cookies
        setup_tokens[account.account_id] = body["mfa_token"]

    setup_headers = {"Authorization": f"Bearer {setup_tokens[admin.account_id]}"}
    assert client.get("/api/v1/auth/me", headers=setup_headers).status_code == 401
    assert client.get("/api/v1/admin/users", headers=setup_headers).status_code == 401

    pending = create_mfa_pending_token({"sub": str(admin.account_id), "email": admin.email, "user_type": "ADMIN"})
    res = client.post("/api/v1/auth/mfa/setup", headers={"Authorization": f"Bearer {pending}"})
    assert res.status_code == 401

    res = client.post("/api/v1/auth/mfa/setup", headers=setup_headers)
    assert res.status_code == 200
    secret = res.json()["secret"]
    res = client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": pyotp.TOTP(secret).now()},
        headers=setup_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert "refresh_token" in res.cookies
    db.expire_all()
    assert admin.is_mfa_enabled is True
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert res.status_code == 200
    assert res.json()["email"] == admin.email
    # The enrolment token is single-purpose once MFA is on.
    assert client.post("/api/v1/auth/mfa/setup", headers=setup_headers).status_code == 401

    res = login(client, employee.email, PASSWORD)
    assert res.status_code == 200
    assert res.json()["access_token"]

    monkeypatch.setattr(settings, "enforce_admin_mfa", False)
    res = login(client, system_admin.email, PASSWORD)
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["mfa_setup_required"] is False
    refresh_token = body["refresh_token"]
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200

    monkeypatch.setattr(settings, "enforce_admin_mfa", True)
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 403
    assert res.json()["detail"] == "MFA setup required"


# ==============================================================================
# Login rate limit (per path and client IP)
# ==============================================================================

def test_login_rate_limit_returns_429(client):
    email = f"nobody-{uuid4().hex[:8]}@example.com"
    for attempt in range(1, LOGIN_RATE_LIMIT + 1):
        res = login(client, email, "WrongPass!")
        assert res.status_code != 429, attempt

    res = login(client, email, "WrongPass!")
    assert res.status_code == 429
    assert res.json()["detail"] == "Too many login attempts. Try again in a minute."
    assert int(res.headers["Retry-After"]) >= 1

    # /mfa/login has its own bucket.
    res = client.post("/api/v1/auth/mfa/login", json={"mfa_token": "not-a-token", "code": "123456"})
    assert res.status_code != 429

def test_mfa_setup_hides_current_otp_in_production(client, db, monkeypatch):
    account = make_account(db, UserType.EMPLOYEE)

    res = client.post("/api/v1/auth/mfa/setup", headers=auth_headers(account))
    assert res.status_code == 200
    assert res.json()["current_otp"]

    monkeypatch.setattr(settings, "env", "production")
    res = client.post("/api/v1/auth/mfa/setup", headers=auth_headers(account))
    assert res.status_code == 200
    assert res.json()["secret"]
    assert res.json()["current_otp"] is None
