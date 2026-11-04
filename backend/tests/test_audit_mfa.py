import os
import sys
from pathlib import Path

# Set testing environment flag and add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ["TESTING"] = "1"

import csv
import io
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # Ensure all SQLAlchemy models are registered
from app.db.session import get_db
from app.main import app
from app.models.enums import UserType, AuditAction
from app.models.user_account import UserAccount
from app.models.audit_log import AuditLog
from app.core.security import hash_password, create_access_token

# Isolated SQLite in-memory test database using StaticPool
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_user(db_session):
    admin = db_session.query(UserAccount).filter(UserAccount.email == "admin@example.com").first()
    if not admin:
        admin = UserAccount(
            account_id=uuid.uuid4(),
            email="admin@example.com",
            password_hash=hash_password("AdminPass123!"),
            user_type=UserType.ADMIN,
            is_active=True,
            is_mfa_enabled=False,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return admin


@pytest.fixture
def employee_user(db_session):
    emp = db_session.query(UserAccount).filter(UserAccount.email == "employee@example.com").first()
    if not emp:
        emp = UserAccount(
            account_id=uuid.uuid4(),
            email="employee@example.com",
            password_hash=hash_password("EmpPass123!"),
            user_type=UserType.EMPLOYEE,
            is_active=True,
            is_mfa_enabled=False,
        )
        db_session.add(emp)
        db_session.commit()
        db_session.refresh(emp)
    return emp


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(
        data={"sub": str(admin_user.account_id), "email": admin_user.email, "user_type": admin_user.user_type.value}
    )


@pytest.fixture
def employee_token(employee_user):
    return create_access_token(
        data={"sub": str(employee_user.account_id), "email": employee_user.email, "user_type": employee_user.user_type.value}
    )


# ---------------------------------------------------------------------------
# Test Suite 1: Audit Log Search and Filtering (US-30, US-47)
# ---------------------------------------------------------------------------

def test_audit_log_filters_and_search(client, db_session, admin_user, admin_token):
    # Clear prior audit logs
    db_session.query(AuditLog).delete()
    db_session.commit()

    now = datetime.now(timezone.utc)
    target_uuid = admin_user.account_id

    # Seed diverse audit log records
    log1 = AuditLog(
        account_id=target_uuid,
        action=AuditAction.CREATE,
        entity_name="PROJECT",
        entity_ref_id="PRJ-101",
        old_value=None,
        new_value='{"name": "Project Alpha"}',
        ip_address="192.168.1.10",
        created_at=now - timedelta(days=2),
    )
    log2 = AuditLog(
        account_id=target_uuid,
        action=AuditAction.UPDATE,
        entity_name="PROJECT",
        entity_ref_id="PRJ-101",
        old_value='{"status": "PLANNED"}',
        new_value='{"status": "ACTIVE"}',
        ip_address="192.168.1.10",
        created_at=now - timedelta(days=1),
    )
    log3 = AuditLog(
        account_id=uuid.uuid4(),
        action=AuditAction.LOGIN,
        entity_name="USER_ACCOUNT",
        entity_ref_id="USR-999",
        old_value=None,
        new_value='{"login": "success"}',
        ip_address="10.0.0.1",
        created_at=now,
    )
    db_session.add_all([log1, log2, log3])
    db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Unfiltered query should return all 3 seeded records
    res = client.get("/api/v1/audit-logs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 2. Filter by account_id
    res = client.get(f"/api/v1/audit-logs?account_id={target_uuid}", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # 3. Filter by entity_name
    res = client.get("/api/v1/audit-logs?entity_name=PROJECT", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # 4. Filter by action
    res = client.get("/api/v1/audit-logs?action=LOGIN", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["entity_name"] == "USER_ACCOUNT"

    # 5. Filter by entity_ref_id
    res = client.get("/api/v1/audit-logs?entity_ref_id=PRJ-101", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # 6. Filter by ip_address
    res = client.get("/api/v1/audit-logs?ip_address=10.0.0.1", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1

    # 7. Search query 'q' matching new_value keyword
    res = client.get("/api/v1/audit-logs?q=Alpha", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["entity_ref_id"] == "PRJ-101"

    # 8. Date range filtering
    start_str = (now - timedelta(days=1, hours=12)).isoformat()
    end_str = (now + timedelta(hours=1)).isoformat()
    res = client.get("/api/v1/audit-logs", params={"start_date": start_str, "end_date": end_str}, headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2


# ---------------------------------------------------------------------------
# Test Suite 2: CSV Export & RBAC (US-47)
# ---------------------------------------------------------------------------

def test_audit_log_export_csv_and_rbac(client, admin_token, employee_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin should successfully download streamed CSV
    res = client.get("/api/v1/audit-logs/export", headers=headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]

    # Parse and verify CSV contents
    csv_text = res.text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) >= 1  # At least header row + records
    expected_header = [
        "log_id", "created_at", "account_id", "action", "entity_name",
        "entity_ref_id", "ip_address", "old_value", "new_value"
    ]
    assert rows[0] == expected_header

    # 2. Filtered CSV export
    res_filtered = client.get("/api/v1/audit-logs/export?action=LOGIN", headers=headers)
    assert res_filtered.status_code == 200
    reader_f = csv.reader(io.StringIO(res_filtered.text))
    rows_f = list(reader_f)
    for r in rows_f[1:]:
        assert r[3] == "LOGIN"

    # 3. RBAC: Non-admin (EMPLOYEE) is blocked from accessing audit logs and export
    emp_headers = {"Authorization": f"Bearer {employee_token}"}
    res_emp = client.get("/api/v1/audit-logs", headers=emp_headers)
    assert res_emp.status_code == 403

    res_emp_export = client.get("/api/v1/audit-logs/export", headers=emp_headers)
    assert res_emp_export.status_code == 403

    # 4. Unauthenticated user is rejected
    res_anon = client.get("/api/v1/audit-logs")
    assert res_anon.status_code == 401


# ---------------------------------------------------------------------------
# Test Suite 3: Admin TOTP MFA Setup, Verification & Status (US-31)
# ---------------------------------------------------------------------------

def test_mfa_setup_and_verify(client, db_session, admin_user, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Check initial MFA status (disabled)
    res_status = client.get("/api/v1/auth/mfa/status", headers=headers)
    assert res_status.status_code == 200
    assert res_status.json()["is_mfa_enabled"] is False

    # 2. Setup MFA
    res_setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert res_setup.status_code == 200
    data = res_setup.json()
    assert "secret" in data
    assert "provisioning_uri" in data
    assert "admin%40example.com" in data["provisioning_uri"] or "admin@example.com" in data["provisioning_uri"]
    secret = data["secret"]

    # Refresh DB model: secret should be saved, but is_mfa_enabled should remain False
    db_session.refresh(admin_user)
    assert admin_user.mfa_secret == secret
    assert admin_user.is_mfa_enabled is False

    # 3. Attempt verification with an incorrect code
    res_verify_fail = client.post(
        "/api/v1/auth/mfa/verify",
        headers=headers,
        json={"code": "000000"},
    )
    assert res_verify_fail.status_code == 400
    assert "Invalid 6-digit MFA code" in res_verify_fail.json()["detail"]

    # 4. Verification with valid code using pyotp
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    res_verify_success = client.post(
        "/api/v1/auth/mfa/verify",
        headers=headers,
        json={"code": valid_code},
    )
    assert res_verify_success.status_code == 200
    assert "MFA has been successfully verified and enabled" in res_verify_success.json()["message"]

    # Refresh DB model: is_mfa_enabled must now be True
    db_session.refresh(admin_user)
    assert admin_user.is_mfa_enabled is True

    # 5. Check status endpoint again
    res_status2 = client.get("/api/v1/auth/mfa/status", headers=headers)
    assert res_status2.status_code == 200
    assert res_status2.json()["is_mfa_enabled"] is True


# ---------------------------------------------------------------------------
# Test Suite 4: Complete MFA Login Challenge Workflow (US-31)
# ---------------------------------------------------------------------------

def test_mfa_login_challenge_flow(client, db_session, admin_user):
    # Ensure admin has MFA enabled with a known secret
    secret = pyotp.random_base32()
    admin_user.mfa_secret = secret
    admin_user.is_mfa_enabled = True
    db_session.commit()

    # 1. Login with valid credentials should trigger MFA challenge
    login_payload = {
        "email": "admin@example.com",
        "password": "AdminPass123!",
    }
    res_login = client.post("/api/v1/auth/login", json=login_payload)
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert login_data["mfa_required"] is True
    assert login_data["mfa_token"] is not None
    assert login_data["access_token"] is None
    mfa_token = login_data["mfa_token"]

    # 2. Complete MFA with incorrect code
    mfa_fail_payload = {
        "mfa_token": mfa_token,
        "code": "999999",
    }
    res_mfa_fail = client.post("/api/v1/auth/mfa/login", json=mfa_fail_payload)
    assert res_mfa_fail.status_code == 401
    assert "Invalid 6-digit MFA code" in res_mfa_fail.json()["detail"]

    # Check security audit log for failed login attempt
    failed_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == AuditAction.LOGIN, AuditLog.new_value.ilike("%mfa_challenge_failed%"))
        .first()
    )
    assert failed_log is not None

    # 3. Complete MFA with invalid/tampered token
    tampered_payload = {
        "mfa_token": "tampered.jwt.token",
        "code": pyotp.TOTP(secret).now(),
    }
    res_tampered = client.post("/api/v1/auth/mfa/login", json=tampered_payload)
    assert res_tampered.status_code == 401

    # 4. Complete MFA with valid TOTP code
    valid_code = pyotp.TOTP(secret).now()
    mfa_success_payload = {
        "mfa_token": mfa_token,
        "code": valid_code,
    }
    res_mfa_success = client.post("/api/v1/auth/mfa/login", json=mfa_success_payload)
    assert res_mfa_success.status_code == 200
    token_data = res_mfa_success.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == "admin@example.com"
    assert token_data["user"]["is_mfa_enabled"] is True

    # Verify refresh_token cookie was set
    assert "refresh_token" in res_mfa_success.cookies

    # Verify success audit log recorded
    success_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == AuditAction.LOGIN, AuditLog.new_value.ilike("%mfa_verified%"))
        .first()
    )
    assert success_log is not None
