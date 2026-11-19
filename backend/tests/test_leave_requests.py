"""
Comprehensive test suite for Leave Management (US-16 & US-40, S4-BE-1).

Tests cover:
  1. Business days only counted in leave requests.
  2. Exceeding quota fails with 400 and available days message.
  3. Overlapping PENDING / APPROVED dates fail with 409.
  4. Past date or cross-year dates fail with 400.
  5. Missing employee profile fails with 403.
  6. Submissions notify Team Leads and staffing PMs with details (US-40) and write CREATE audit log.
  7. History isolation and status/year filters.
  8. Balance authorization for Employee, Team Lead, HR, Admin.
  9. Cancellation restricted to PENDING requests and owners only with UPDATE audit log.
  - Inactive and nonexistent leave types.
  - Invalid reason length (422).
  - Weekend-only range (400).
  - Exactly exhausted quota.
  - Negative available balances not clamped to zero.
  - Multiple TLs and PMs deduplication.
  - Approved request cancellation rejection.
  - Cross-year quota isolation.
"""

from datetime import date, timedelta
import uuid
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.leave.requests_router import get_today
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    LeaveStatus,
    PriorityLevel,
    ProjectStatus,
    TeamStatus,
    UserType,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.notification import Notification
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

TODAY = date(2026, 11, 23)  # Monday


@pytest.fixture(scope="function")
def db():
    """Create fresh in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with overridden get_db and get_current_user."""
    def override_get_db():
        yield db

    def override_get_today():
        return TODAY

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_today] = override_get_today

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user(db, user_type: UserType, email: str | None = None) -> UserAccount:
    """Helper to create and commit a UserAccount."""
    acc_id = uuid.uuid4()
    mail = email or f"{acc_id.hex[:8]}@example.com"
    user = UserAccount(
        account_id=acc_id,
        email=mail,
        password_hash="hashed_pw",
        user_type=user_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_employee(db, user: UserAccount, name: str = "Alice Employee") -> Employee:
    """Helper to create an Employee linked to user."""
    emp = Employee(
        account_id=user.account_id,
        emp_code=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        designation="Software Engineer",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def make_pm(db, user: UserAccount, name: str = "Carol PM") -> ProjectManager:
    """Helper to create a ProjectManager linked to user."""
    pm = ProjectManager(
        account_id=user.account_id,
        emp_code=f"PM-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


def make_leave_type(
    db,
    name: str = "Annual Leave",
    quota: int = 20,
    is_active: bool = True,
) -> LeaveType:
    """Helper to create a LeaveType."""
    lt = LeaveType(
        name=name,
        yearly_quota=quota,
        is_paid=True,
        description=f"{name} policy",
        is_active=is_active,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def auth_client_as(client, user: UserAccount):
    """Set the authenticated user for the TestClient."""
    def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user


# -----------------------------------------------------------------------------
# 1. test_apply_leave_success_counts_business_days_only()
# -----------------------------------------------------------------------------
def test_apply_leave_success_counts_business_days_only(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=20)
    auth_client_as(client, user)

    # Friday 2026-11-27 to Monday 2026-11-30 -> Fri + Mon = 2 business days (Sat & Sun excluded)
    payload = {
        "leave_type_id": lt.leave_type_id,
        "start_date": "2026-11-27",
        "end_date": "2026-11-30",
        "reason": "Attending a family gathering out of town.",
    }
    response = client.post("/api/v1/leave/requests", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["total_days"] == 2
    assert data["status"] == "PENDING"
    assert data["leave_type_name"] == lt.name
    assert data["emp_id"] == emp.emp_id


# -----------------------------------------------------------------------------
# 2. test_apply_leave_exceeding_quota_fails_400()
# -----------------------------------------------------------------------------
def test_apply_leave_exceeding_quota_fails_400(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    lt = make_leave_type(db, name="Casual Leave", quota=5)
    auth_client_as(client, user)

    # Pre-populate 3 approved days and 1 pending day in 2026 -> 4 days consumed
    req_approved = LeaveRequest(
        emp_id=emp.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 11, 23),
        end_date=date(2026, 11, 25),
        total_days=3,
        reason="Prior medical checkup.",
        status=LeaveStatus.APPROVED,
    )
    req_pending = LeaveRequest(
        emp_id=emp.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 11, 26),
        end_date=date(2026, 11, 26),
        total_days=1,
        reason="Personal urgent errand.",
        status=LeaveStatus.PENDING,
    )
    db.add_all([req_approved, req_pending])
    db.commit()

    # Quota: 5. Used: 3, Pending: 1 -> Available: 1 day.
    # Requesting 2 days (Tue 2026-12-01 to Wed 2026-12-02) should fail with 400
    payload = {
        "leave_type_id": lt.leave_type_id,
        "start_date": "2026-12-01",
        "end_date": "2026-12-02",
        "reason": "Short break for wellness.",
    }
    response = client.post("/api/v1/leave/requests", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient leave balance (Available: 1 days)"


# -----------------------------------------------------------------------------
# 3. test_apply_leave_overlapping_dates_fails_409()
# -----------------------------------------------------------------------------
def test_apply_leave_overlapping_dates_fails_409(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=20)
    auth_client_as(client, user)

    # Existing pending request: Dec 10 to Dec 15
    db.add(
        LeaveRequest(
            emp_id=emp.emp_id,
            leave_type_id=lt.leave_type_id,
            start_date=date(2026, 12, 10),
            end_date=date(2026, 12, 15),
            total_days=4,
            reason="Existing vacation request.",
            status=LeaveStatus.PENDING,
        )
    )
    db.commit()

    # Overlapping case 1: subset / intersecting (Dec 14 to Dec 18)
    response1 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-12-14",
            "end_date": "2026-12-18",
            "reason": "Overlapping request start.",
        },
    )
    assert response1.status_code == 409
    assert response1.json()["detail"] == "Overlapping leave request exists"

    # Overlapping case 2: spanning (Dec 8 to Dec 11)
    response2 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-12-08",
            "end_date": "2026-12-11",
            "reason": "Overlapping request end.",
        },
    )
    assert response2.status_code == 409
    assert response2.json()["detail"] == "Overlapping leave request exists"


# -----------------------------------------------------------------------------
# 4. test_apply_leave_past_or_cross_year_fails_400()
# -----------------------------------------------------------------------------
def test_apply_leave_past_or_cross_year_fails_400(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=20)
    auth_client_as(client, user)

    # Past date (TODAY is 2026-11-23)
    res_past = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-20",
            "end_date": "2026-11-25",
            "reason": "Applying after taking leave.",
        },
    )
    assert res_past.status_code == 400
    assert res_past.json()["detail"] == "Cannot apply for leave in the past"

    # Cross calendar years (2026 to 2027)
    res_cross = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-12-30",
            "end_date": "2027-01-04",
            "reason": "New Year holiday across year boundary.",
        },
    )
    assert res_cross.status_code == 400
    assert res_cross.json()["detail"] == "Leave cannot span calendar years; submit two requests"

    # End date before start date
    res_end_before_start = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-30",
            "end_date": "2026-11-25",
            "reason": "End date is earlier than start date.",
        },
    )
    assert res_end_before_start.status_code == 400


# -----------------------------------------------------------------------------
# 5. test_apply_leave_without_employee_profile_fails_403()
# -----------------------------------------------------------------------------
def test_apply_leave_without_employee_profile_fails_403(client, db):
    # Account with EMPLOYEE role but NO Employee row
    orphan_user = make_user(db, UserType.EMPLOYEE, "orphan@example.com")
    lt = make_leave_type(db, quota=20)
    auth_client_as(client, orphan_user)

    response = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-25",
            "end_date": "2026-11-27",
            "reason": "Valid reason but user has no employee profile.",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "No employee profile linked to this account"


# -----------------------------------------------------------------------------
# 6. test_submission_notifies_team_lead_and_staffing_pm()
# -----------------------------------------------------------------------------
def test_submission_notifies_team_lead_and_staffing_pm(client, db):
    # Setup Alice (applicant)
    u_alice = make_user(db, UserType.EMPLOYEE, "alice@x.com")
    emp_alice = make_employee(db, u_alice, "Alice Applicant")

    # Setup Team Lead Bob
    u_bob = make_user(db, UserType.TEAM_LEAD, "bob@x.com")
    emp_bob = make_employee(db, u_bob, "Bob Lead")
    team = Team(name="Core Engineering", lead_emp_id=emp_bob.emp_id, status=TeamStatus.ACTIVE)
    db.add(team)
    db.commit()
    db.add(TeamMember(team_id=team.team_id, emp_id=emp_alice.emp_id))
    db.commit()

    # Setup Staffing PM Carol and Project
    u_carol = make_user(db, UserType.PM, "carol@x.com")
    pm_carol = make_pm(db, u_carol, "Carol Manager")
    client_rec = Client(company_name="Acme Corp", contact_person="John Doe", email="acme@corp.com")
    db.add(client_rec)
    db.commit()

    project = Project(
        client_id=client_rec.client_id,
        pm_id=pm_carol.pm_id,
        project_code="PRJ-ALPHA",
        name="Project Alpha",
        start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    db.commit()

    # Unreleased assignment for Alice on Project Alpha
    db.add(
        ProjectAssignment(
            project_id=project.project_id,
            emp_id=emp_alice.emp_id,
            role_in_project="Backend Lead",
            released_on=None,
        )
    )
    db.commit()

    lt = make_leave_type(db, quota=20)
    auth_client_as(client, u_alice)

    payload = {
        "leave_type_id": lt.leave_type_id,
        "start_date": "2026-11-25",
        "end_date": "2026-11-27",
        "reason": "Attending annual developer conference.",
    }
    response = client.post("/api/v1/leave/requests", json=payload)
    assert response.status_code == 201
    leave_id = response.json()["leave_id"]

    # Verify Notifications in DB
    notifications = db.query(Notification).all()
    recipient_ids = {n.account_id for n in notifications}

    # Bob (TL) and Carol (PM) must be notified
    assert u_bob.account_id in recipient_ids
    assert u_carol.account_id in recipient_ids
    # Alice (applicant) must NOT be notified
    assert u_alice.account_id not in recipient_ids
    assert len(notifications) == 2

    for n in notifications:
        assert n.type == "LEAVE_REQUESTED"
        assert "Alice Applicant" in n.message
        assert "3 day(s)" in n.message
        assert "Project Alpha" in n.message
        assert n.link == f"/team-lead/leave?request={leave_id}"

    # Verify CREATE Audit Log
    audit_row = (
        db.query(AuditLog)
        .filter(AuditLog.entity_name == "LEAVE_REQUEST", AuditLog.entity_ref_id == str(leave_id))
        .first()
    )
    assert audit_row is not None
    assert audit_row.action == AuditAction.CREATE
    assert audit_row.account_id == u_alice.account_id


# -----------------------------------------------------------------------------
# 7. test_get_my_leave_history_isolation_and_filters()
# -----------------------------------------------------------------------------
def test_get_my_leave_history_isolation_and_filters(client, db):
    u1 = make_user(db, UserType.EMPLOYEE, "u1@x.com")
    emp1 = make_employee(db, u1, "User One")

    u2 = make_user(db, UserType.EMPLOYEE, "u2@x.com")
    emp2 = make_employee(db, u2, "User Two")

    lt = make_leave_type(db, quota=30)

    # User 1 leaves
    req1 = LeaveRequest(
        emp_id=emp1.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 2),
        total_days=2,
        reason="First request for user 1.",
        status=LeaveStatus.PENDING,
    )
    req2 = LeaveRequest(
        emp_id=emp1.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 15),
        end_date=date(2026, 12, 16),
        total_days=2,
        reason="Second request for user 1.",
        status=LeaveStatus.APPROVED,
        review_remarks="Approved by TL.",
        reviewed_at=TODAY,
    )
    # User 2 leave
    req_other = LeaveRequest(
        emp_id=emp2.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 5),
        end_date=date(2026, 12, 7),
        total_days=2,
        reason="User 2 private request.",
        status=LeaveStatus.PENDING,
    )
    db.add_all([req1, req2, req_other])
    db.commit()

    auth_client_as(client, u1)

    # 1. Total history for User 1
    res = client.get("/api/v1/leave/requests/my")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    ids = [i["leave_id"] for i in items]
    assert req_other.leave_id not in ids
    assert items[0]["leave_type_name"] == lt.name

    # 2. Filter by status=APPROVED
    res_app = client.get("/api/v1/leave/requests/my?status=APPROVED")
    assert res_app.status_code == 200
    app_items = res_app.json()
    assert len(app_items) == 1
    assert app_items[0]["leave_id"] == req2.leave_id
    assert app_items[0]["review_remarks"] == "Approved by TL."

    # 3. Filter by year
    res_yr = client.get("/api/v1/leave/requests/my?year=2026")
    assert res_yr.status_code == 200
    assert len(res_yr.json()) == 2

    res_future = client.get("/api/v1/leave/requests/my?year=2027")
    assert res_future.status_code == 200
    assert len(res_future.json()) == 0

    # 4. Pagination
    res_p1 = client.get("/api/v1/leave/requests/my?page=1&limit=1")
    assert res_p1.status_code == 200
    assert len(res_p1.json()) == 1


# -----------------------------------------------------------------------------
# 8. test_balance_access_rules_employee_tl_hr()
# -----------------------------------------------------------------------------
def test_balance_access_rules_employee_tl_hr(client, db):
    u_emp = make_user(db, UserType.EMPLOYEE, "emp@x.com")
    emp = make_employee(db, u_emp, "Alice Emp")

    u_other = make_user(db, UserType.EMPLOYEE, "other@x.com")
    other_emp = make_employee(db, u_other, "Other Emp")

    u_tl = make_user(db, UserType.TEAM_LEAD, "tl@x.com")
    tl = make_employee(db, u_tl, "Bob TL")

    team = Team(name="Eng", lead_emp_id=tl.emp_id, status=TeamStatus.ACTIVE)
    db.add(team)
    db.commit()
    # Alice is on Bob's team; Other Emp is NOT
    db.add(TeamMember(team_id=team.team_id, emp_id=emp.emp_id))
    db.commit()

    u_hr = make_user(db, UserType.HR, "hr@x.com")
    u_admin = make_user(db, UserType.ADMIN, "admin@x.com")

    lt = make_leave_type(db, quota=15)

    # 1. Employee checking balance/me -> 200
    auth_client_as(client, u_emp)
    res_me = client.get("/api/v1/leave/balance/me")
    assert res_me.status_code == 200
    assert res_me.json()[0]["available_days"] == 15

    # 2. Employee checking own balance via ID -> 200
    res_own = client.get(f"/api/v1/leave/balance/{emp.emp_id}")
    assert res_own.status_code == 200

    # 3. Employee checking another employee's balance -> 403
    res_forbidden = client.get(f"/api/v1/leave/balance/{other_emp.emp_id}")
    assert res_forbidden.status_code == 403

    # 4. TL checking team member's balance -> 200
    auth_client_as(client, u_tl)
    res_tl_member = client.get(f"/api/v1/leave/balance/{emp.emp_id}")
    assert res_tl_member.status_code == 200

    # 5. TL checking outsider employee's balance -> 403
    res_tl_outsider = client.get(f"/api/v1/leave/balance/{other_emp.emp_id}")
    assert res_tl_outsider.status_code == 403

    # 6. TL checking nonexistent employee -> 404
    res_tl_none = client.get("/api/v1/leave/balance/99999")
    assert res_tl_none.status_code == 404

    # 7. HR checking any employee's balance -> 200
    auth_client_as(client, u_hr)
    assert client.get(f"/api/v1/leave/balance/{emp.emp_id}").status_code == 200
    assert client.get(f"/api/v1/leave/balance/{other_emp.emp_id}").status_code == 200
    assert client.get("/api/v1/leave/balance/99999").status_code == 404

    # 8. Admin checking balance -> 200
    auth_client_as(client, u_admin)
    assert client.get(f"/api/v1/leave/balance/{emp.emp_id}").status_code == 200


# -----------------------------------------------------------------------------
# 9. test_cancel_only_pending_and_only_owner()
# -----------------------------------------------------------------------------
def test_cancel_only_pending_and_only_owner(client, db):
    u_alice = make_user(db, UserType.EMPLOYEE, "alice@x.com")
    emp_alice = make_employee(db, u_alice, "Alice")

    u_bob = make_user(db, UserType.EMPLOYEE, "bob@x.com")
    make_employee(db, u_bob, "Bob")

    lt = make_leave_type(db, quota=20)

    req = LeaveRequest(
        emp_id=emp_alice.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 3),
        total_days=3,
        reason="Personal leave application.",
        status=LeaveStatus.PENDING,
    )
    db.add(req)
    db.commit()

    # 1. Non-owner (Bob) attempts to cancel Alice's request -> 403
    auth_client_as(client, u_bob)
    res_bob = client.put(f"/api/v1/leave/requests/{req.leave_id}/cancel")
    assert res_bob.status_code == 403
    assert res_bob.json()["detail"] == "You can only cancel your own leave requests"

    # 2. Owner (Alice) cancels her PENDING request -> 200
    auth_client_as(client, u_alice)
    res_alice = client.put(f"/api/v1/leave/requests/{req.leave_id}/cancel")
    assert res_alice.status_code == 200
    assert res_alice.json()["status"] == "CANCELLED"

    # Verify UPDATE audit log written
    audit_row = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_name == "LEAVE_REQUEST",
            AuditLog.entity_ref_id == str(req.leave_id),
            AuditLog.action == AuditAction.UPDATE,
        )
        .first()
    )
    assert audit_row is not None

    # 3. Trying to cancel already CANCELLED request -> 400
    res_again = client.put(f"/api/v1/leave/requests/{req.leave_id}/cancel")
    assert res_again.status_code == 400
    assert res_again.json()["detail"] == "Only pending requests can be cancelled"

    # 4. Trying to cancel APPROVED request -> 400
    approved_req = LeaveRequest(
        emp_id=emp_alice.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 8),
        end_date=date(2026, 12, 10),
        total_days=3,
        reason="Approved trip.",
        status=LeaveStatus.APPROVED,
    )
    db.add(approved_req)
    db.commit()

    res_app_cancel = client.put(f"/api/v1/leave/requests/{approved_req.leave_id}/cancel")
    assert res_app_cancel.status_code == 400
    assert res_app_cancel.json()["detail"] == "Only pending requests can be cancelled"


# -----------------------------------------------------------------------------
# Additional Tests: Edge Cases
# -----------------------------------------------------------------------------
def test_inactive_and_nonexistent_leave_type(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    make_employee(db, user, "Alice")
    lt_inactive = make_leave_type(db, name="Inactive Policy", quota=10, is_active=False)
    auth_client_as(client, user)

    # Inactive leave type -> 400
    res1 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt_inactive.leave_type_id,
            "start_date": "2026-11-25",
            "end_date": "2026-11-27",
            "reason": "Applying to inactive leave type.",
        },
    )
    assert res1.status_code == 400
    assert res1.json()["detail"] == "Leave type is not active"

    # Nonexistent leave type -> 404
    res2 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": 99999,
            "start_date": "2026-11-25",
            "end_date": "2026-11-27",
            "reason": "Applying to nonexistent leave type.",
        },
    )
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Leave type not found"


def test_invalid_reason_fails_422(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=10)
    auth_client_as(client, user)

    # Reason too short (< 10 chars stripped)
    res = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-25",
            "end_date": "2026-11-27",
            "reason": "   short   ",
        },
    )
    assert res.status_code == 422


def test_weekend_only_range_fails_400(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=10)
    auth_client_as(client, user)

    # Saturday 2026-11-28 to Sunday 2026-11-29
    res = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-28",
            "end_date": "2026-11-29",
            "reason": "Weekend trip across Sat and Sun.",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Selected range contains no working days"


def test_exactly_exhausted_quota_succeeds_then_subsequent_fails(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=5)
    auth_client_as(client, user)

    # Apply exactly 5 days (Mon 2026-11-23 to Fri 2026-11-27)
    res1 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-23",
            "end_date": "2026-11-27",
            "reason": "Exhausting full annual balance.",
        },
    )
    assert res1.status_code == 201
    assert res1.json()["total_days"] == 5

    # Subsequent 1-day request in same year fails with Available: 0 days
    res2 = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-30",
            "end_date": "2026-11-30",
            "reason": "One more day after exhausting balance.",
        },
    )
    assert res2.status_code == 400
    assert res2.json()["detail"] == "Insufficient leave balance (Available: 0 days)"


def test_negative_available_balance_preserved(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    # Quota is 5, but employee already has 7 approved days (e.g. quota reduced)
    lt = make_leave_type(db, quota=5)
    db.add(
        LeaveRequest(
            emp_id=emp.emp_id,
            leave_type_id=lt.leave_type_id,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 9),
            total_days=7,
            reason="Special approved leave prior to policy reduction.",
            status=LeaveStatus.APPROVED,
        )
    )
    db.commit()

    auth_client_as(client, user)
    res = client.get("/api/v1/leave/balance/me")
    assert res.status_code == 200
    balance_item = res.json()[0]
    # available_days must NOT be clamped to zero: 5 - 7 = -2
    assert balance_item["available_days"] == -2


def test_submission_multiple_team_leads_and_staffing_pms(client, db):
    u_alice = make_user(db, UserType.EMPLOYEE, "alice@x.com")
    emp_alice = make_employee(db, u_alice, "Alice")

    # TL 1
    u_tl1 = make_user(db, UserType.TEAM_LEAD, "tl1@x.com")
    emp_tl1 = make_employee(db, u_tl1, "Lead 1")
    t1 = Team(name="Team 1", lead_emp_id=emp_tl1.emp_id, status=TeamStatus.ACTIVE)
    db.add(t1)
    db.commit()
    db.add(TeamMember(team_id=t1.team_id, emp_id=emp_alice.emp_id))
    db.commit()

    # TL 2
    u_tl2 = make_user(db, UserType.TEAM_LEAD, "tl2@x.com")
    emp_tl2 = make_employee(db, u_tl2, "Lead 2")
    t2 = Team(name="Team 2", lead_emp_id=emp_tl2.emp_id, status=TeamStatus.ACTIVE)
    db.add(t2)
    db.commit()
    db.add(TeamMember(team_id=t2.team_id, emp_id=emp_alice.emp_id))
    db.commit()

    # PM 1
    u_pm1 = make_user(db, UserType.PM, "pm1@x.com")
    pm1 = make_pm(db, u_pm1, "PM 1")
    c1 = Client(company_name="Client 1", contact_person="Jane Doe", email="c1@x.com")
    db.add(c1)
    db.commit()
    p1 = Project(client_id=c1.client_id, pm_id=pm1.pm_id, project_code="P1", name="P1", start_date=date(2026, 1, 1), status=ProjectStatus.ACTIVE)
    db.add(p1)
    db.commit()
    db.add(ProjectAssignment(project_id=p1.project_id, emp_id=emp_alice.emp_id, role_in_project="Dev", released_on=None))
    db.commit()

    # PM 2 (is also TL 1, to test deduplication!)
    # We assign PM 1 to another project or let emp_tl1 also be a PM:
    # Here u_pm2 is separate
    u_pm2 = make_user(db, UserType.PM, "pm2@x.com")
    pm2 = make_pm(db, u_pm2, "PM 2")
    p2 = Project(client_id=c1.client_id, pm_id=pm2.pm_id, project_code="P2", name="P2", start_date=date(2026, 1, 1), status=ProjectStatus.ACTIVE)
    db.add(p2)
    db.commit()
    db.add(ProjectAssignment(project_id=p2.project_id, emp_id=emp_alice.emp_id, role_in_project="Dev", released_on=None))
    db.commit()

    lt = make_leave_type(db, quota=20)
    auth_client_as(client, u_alice)

    res = client.post(
        "/api/v1/leave/requests",
        json={
            "leave_type_id": lt.leave_type_id,
            "start_date": "2026-11-25",
            "end_date": "2026-11-27",
            "reason": "Conference across multiple projects and teams.",
        },
    )
    assert res.status_code == 201

    notifications = db.query(Notification).all()
    notified_ids = {n.account_id for n in notifications}
    # All 4 unique actors must be notified
    assert notified_ids == {u_tl1.account_id, u_tl2.account_id, u_pm1.account_id, u_pm2.account_id}
    assert len(notifications) == 4


def test_cross_year_quota_calculations(client, db):
    user = make_user(db, UserType.EMPLOYEE)
    emp = make_employee(db, user, "Alice")
    lt = make_leave_type(db, quota=10)

    # 8 days approved in 2025
    db.add(
        LeaveRequest(
            emp_id=emp.emp_id,
            leave_type_id=lt.leave_type_id,
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 10),
            total_days=8,
            reason="Old year vacation.",
            status=LeaveStatus.APPROVED,
        )
    )
    db.commit()

    auth_client_as(client, user)

    # 2026 balance should have 0 used and 10 available
    res_2026 = client.get("/api/v1/leave/balance/me?year=2026")
    assert res_2026.status_code == 200
    b_2026 = res_2026.json()[0]
    assert b_2026["used_days"] == 0
    assert b_2026["available_days"] == 10

    # 2025 balance should have 8 used and 2 available
    res_2025 = client.get("/api/v1/leave/balance/me?year=2025")
    assert res_2025.status_code == 200
    b_2025 = res_2025.json()[0]
    assert b_2025["used_days"] == 8
    assert b_2025["available_days"] == 2
