import uuid
from datetime import datetime, timezone
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.models.support import SupportTicket, TicketActivity
from app.models.notification import Notification
from app.models.enums import UserType, CommonStatus


@pytest.fixture(scope="function")
def db_session():
    """Create fresh in-memory database and yield session."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db and get_current_user dependencies."""
    def override_get_db():
        yield db_session

    def override_get_current_user(request: Request):
        x_user_id = request.headers.get("X-User-Id")
        if x_user_id:
            user = db_session.query(UserAccount).filter(UserAccount.account_id == uuid.UUID(x_user_id)).first()
            if user:
                return user
        return db_session.query(UserAccount).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_data(db_session):
    """Seed test accounts and employees across roles."""
    emp1_acc = UserAccount(
        account_id=uuid.UUID("a0000001-0000-0000-0000-000000000001"),
        email="alice.employee@company.com",
        password_hash="pw1",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp2_acc = UserAccount(
        account_id=uuid.UUID("a0000002-0000-0000-0000-000000000002"),
        email="bob.employee@company.com",
        password_hash="pw2",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    it_support1_acc = UserAccount(
        account_id=uuid.UUID("b0000001-0000-0000-0000-000000000001"),
        email="charlie.it@company.com",
        password_hash="pw3",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    it_support2_acc = UserAccount(
        account_id=uuid.UUID("b0000002-0000-0000-0000-000000000002"),
        email="dave.it@company.com",
        password_hash="pw4",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    sysadmin_acc = UserAccount(
        account_id=uuid.UUID("c0000001-0000-0000-0000-000000000001"),
        email="eve.sysadmin@company.com",
        password_hash="pw5",
        user_type=UserType.SYSTEM_ADMIN,
        is_active=True,
    )

    db_session.add_all([emp1_acc, emp2_acc, it_support1_acc, it_support2_acc, sysadmin_acc])
    db_session.flush()

    emp1 = Employee(
        account_id=emp1_acc.account_id,
        emp_code="EMP-001",
        full_name="Alice Smith",
        email=emp1_acc.email,
        designation="Software Engineer",
        date_of_joining=datetime.now().date(),
        status=CommonStatus.ACTIVE,
    )
    emp2 = Employee(
        account_id=emp2_acc.account_id,
        emp_code="EMP-002",
        full_name="Bob Jones",
        email=emp2_acc.email,
        designation="QA Engineer",
        date_of_joining=datetime.now().date(),
        status=CommonStatus.ACTIVE,
    )
    it_emp1 = Employee(
        account_id=it_support1_acc.account_id,
        emp_code="IT-001",
        full_name="Charlie Brown",
        email=it_support1_acc.email,
        designation="IT Support Specialist",
        date_of_joining=datetime.now().date(),
        status=CommonStatus.ACTIVE,
    )
    it_emp2 = Employee(
        account_id=it_support2_acc.account_id,
        emp_code="IT-002",
        full_name="Dave Wilson",
        email=it_support2_acc.email,
        designation="IT Support Lead",
        date_of_joining=datetime.now().date(),
        status=CommonStatus.ACTIVE,
    )
    sys_emp = Employee(
        account_id=sysadmin_acc.account_id,
        emp_code="SYS-001",
        full_name="Eve Adams",
        email=sysadmin_acc.email,
        designation="Principal System Administrator",
        date_of_joining=datetime.now().date(),
        status=CommonStatus.ACTIVE,
    )

    db_session.add_all([emp1, emp2, it_emp1, it_emp2, sys_emp])
    db_session.commit()

    return {
        "emp1": emp1_acc,
        "emp2": emp2_acc,
        "it1": it_support1_acc,
        "it2": it_support2_acc,
        "sysadmin": sysadmin_acc,
    }


# =============================================================================
# 1. test_queue_filters_and_pagination
# =============================================================================

def test_queue_filters_and_pagination(client, db_session, seed_data):
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}

    # Seed 4 tickets with distinct priorities and categories
    now = datetime.now(timezone.utc)
    t1 = SupportTicket(
        ticket_number="TKT-101",
        subject="Low priority doc issue",
        description="Docs typo",
        category="other",
        priority="LOW",
        status="open",
        reporter_id=seed_data["emp1"].account_id,
        created_at=now,
    )
    t2 = SupportTicket(
        ticket_number="TKT-102",
        subject="Critical production crash",
        description="Core service failing",
        category="software",
        priority="CRITICAL",
        status="open",
        reporter_id=seed_data["emp2"].account_id,
        created_at=now,
    )
    t3 = SupportTicket(
        ticket_number="TKT-103",
        subject="High priority router issue",
        description="VPN tunnel dropped",
        category="network",
        priority="HIGH",
        status="in_progress",
        reporter_id=seed_data["emp1"].account_id,
        assigned_to=seed_data["it1"].account_id,
        created_at=now,
    )
    t4 = SupportTicket(
        ticket_number="TKT-104",
        subject="Medium priority monitor issue",
        description="Flickering screen",
        category="hardware",
        priority="MEDIUM",
        status="open",
        reporter_id=seed_data["emp2"].account_id,
        created_at=now,
    )
    db_session.add_all([t1, t2, t3, t4])
    db_session.commit()

    # 1. Priority sorting: CRITICAL must be first
    res = client.get("/api/v1/support/tickets", headers=it1_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    items = data["items"]
    assert items[0]["ticket_number"] == "TKT-102"  # CRITICAL is first
    assert items[1]["ticket_number"] == "TKT-103"  # HIGH is second

    # 2. Filter by status
    res_status = client.get("/api/v1/support/tickets?status=in_progress", headers=it1_headers)
    assert res_status.status_code == 200
    assert res_status.json()["total"] == 1
    assert res_status.json()["items"][0]["ticket_number"] == "TKT-103"

    # 3. Filter by category
    res_cat = client.get("/api/v1/support/tickets?category=network", headers=it1_headers)
    assert res_cat.status_code == 200
    assert res_cat.json()["total"] == 1
    assert res_cat.json()["items"][0]["category"] == "network"

    # 4. Filter by priority
    res_pri = client.get("/api/v1/support/tickets?priority=CRITICAL", headers=it1_headers)
    assert res_pri.status_code == 200
    assert res_pri.json()["total"] == 1
    assert res_pri.json()["items"][0]["priority"] == "CRITICAL"

    # 5. Filter by assigned_to=me
    res_me = client.get("/api/v1/support/tickets?assigned_to=me", headers=it1_headers)
    assert res_me.status_code == 200
    assert res_me.json()["total"] == 1
    assert res_me.json()["items"][0]["ticket_number"] == "TKT-103"

    # 6. Filter by assigned_to=unassigned
    res_unassigned = client.get("/api/v1/support/tickets?assigned_to=unassigned", headers=it1_headers)
    assert res_unassigned.status_code == 200
    assert res_unassigned.json()["total"] == 3

    # 7. Pagination: page 1 limit 2
    res_page = client.get("/api/v1/support/tickets?page=1&limit=2", headers=it1_headers)
    assert res_page.status_code == 200
    pdata = res_page.json()
    assert len(pdata["items"]) == 2
    assert pdata["total"] == 4
    assert pdata["page"] == 1
    assert pdata["limit"] == 2

    # 8. Metrics endpoint
    res_metrics = client.get("/api/v1/support/tickets/queue/metrics", headers=it1_headers)
    assert res_metrics.status_code == 200
    mdata = res_metrics.json()
    assert mdata["total"] == 4
    assert mdata["open"] == 3
    assert mdata["in_progress"] == 1
    assert mdata["unassigned"] == 3


# =============================================================================
# 2. test_queue_forbidden_for_employee
# =============================================================================

def test_queue_forbidden_for_employee(client, seed_data):
    emp_headers = {"X-User-Id": str(seed_data["emp1"].account_id)}

    res_queue = client.get("/api/v1/support/tickets", headers=emp_headers)
    assert res_queue.status_code == 403

    res_metrics = client.get("/api/v1/support/tickets/queue/metrics", headers=emp_headers)
    assert res_metrics.status_code == 403

    res_assign = client.put(
        "/api/v1/support/tickets/1/assign",
        json={"assignee_account_id": str(seed_data["it1"].account_id)},
        headers=emp_headers,
    )
    assert res_assign.status_code == 403

    res_notes = client.post(
        "/api/v1/support/tickets/1/notes",
        json={"note": "Internal employee note"},
        headers=emp_headers,
    )
    assert res_notes.status_code == 403


# =============================================================================
# 3. test_assign_requires_it_staff_assignee
# =============================================================================

def test_assign_requires_it_staff_assignee(client, db_session, seed_data):
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}

    # Create an open ticket
    ticket = SupportTicket(
        ticket_number="TKT-201",
        subject="Printer offline",
        description="Floor 2 printer is showing error code 55",
        category="hardware",
        priority="MEDIUM",
        status="open",
        reporter_id=seed_data["emp1"].account_id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    # 1. Assign to employee -> 400 Bad Request
    res_bad_assignee = client.put(
        f"/api/v1/support/tickets/{ticket.id}/assign",
        json={"assignee_account_id": str(seed_data["emp2"].account_id)},
        headers=it1_headers,
    )
    assert res_bad_assignee.status_code == 400
    assert "IT Support or System Administrator" in res_bad_assignee.json()["detail"]

    # 2. Assign to nonexistent UUID -> 400 Bad Request
    res_not_found = client.put(
        f"/api/v1/support/tickets/{ticket.id}/assign",
        json={"assignee_account_id": str(uuid.uuid4())},
        headers=it1_headers,
    )
    assert res_not_found.status_code == 400

    # 3. Assign to IT Support staff -> 200 OK, transitions open -> in_progress
    res_ok = client.put(
        f"/api/v1/support/tickets/{ticket.id}/assign",
        json={"assignee_account_id": str(seed_data["it2"].account_id)},
        headers=it1_headers,
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["status"] == "in_progress"
    assert data["assigned_to"] == str(seed_data["it2"].account_id)

    # Verify ASSIGNED activity
    db_session.refresh(ticket)
    activities = [a for a in ticket.activities if a.action == "ASSIGNED"]
    assert len(activities) >= 1
    assert "Dave Wilson" in activities[0].note

    # Verify notification created for assignee
    notif = (
        db_session.query(Notification)
        .filter(Notification.account_id == seed_data["it2"].account_id)
        .first()
    )
    assert notif is not None
    assert notif.type == "TICKET_ASSIGNED"


# =============================================================================
# 4. test_status_machine_rejects_invalid_transitions
# =============================================================================

def test_status_machine_rejects_invalid_transitions(client, db_session, seed_data):
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}
    emp1_headers = {"X-User-Id": str(seed_data["emp1"].account_id)}

    ticket = SupportTicket(
        ticket_number="TKT-301",
        subject="Application bug",
        description="Submit button does not click",
        category="software",
        priority="HIGH",
        status="open",
        reporter_id=seed_data["emp1"].account_id,
        assigned_to=seed_data["it1"].account_id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    # 1. Target cannot be escalated via status endpoint -> 409 Conflict
    res_escalate = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "escalated"},
        headers=it1_headers,
    )
    assert res_escalate.status_code == 409

    # 2. Invalid direct transition: open -> resolved -> 409 Conflict
    res_direct_resolve = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "resolved", "resolution_note": "Fixed"},
        headers=it1_headers,
    )
    assert res_direct_resolve.status_code == 409

    # 3. Valid transition: open -> in_progress
    res_in_prog = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "in_progress"},
        headers=it1_headers,
    )
    assert res_in_prog.status_code == 200
    assert res_in_prog.json()["status"] == "in_progress"

    # 4. in_progress -> resolved without resolution_note -> 400 Bad Request
    res_no_note = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "resolved"},
        headers=it1_headers,
    )
    assert res_no_note.status_code == 400
    assert "Resolution note is mandatory" in res_no_note.json()["detail"]

    # 5. in_progress -> resolved with resolution_note -> 200 OK
    res_resolved = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "resolved", "resolution_note": "Patched client-side JS event handler."},
        headers=it1_headers,
    )
    assert res_resolved.status_code == 200
    assert res_resolved.json()["status"] == "resolved"
    assert res_resolved.json()["resolved_at"] is not None

    # 6. Reporter can reopen their own resolved ticket to open
    res_reopen = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "open"},
        headers=emp1_headers,
    )
    assert res_reopen.status_code == 200
    assert res_reopen.json()["status"] == "open"
    assert res_reopen.json()["resolved_at"] is None

    # 7. Reporter attempting to transition open -> closed -> 403 Forbidden
    res_rep_close = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "closed"},
        headers=emp1_headers,
    )
    assert res_rep_close.status_code == 403


# =============================================================================
# 5. test_only_sysadmin_resolves_escalated
# =============================================================================

def test_only_sysadmin_resolves_escalated(client, db_session, seed_data):
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}
    sys_headers = {"X-User-Id": str(seed_data["sysadmin"].account_id)}

    ticket = SupportTicket(
        ticket_number="TKT-401",
        subject="Database lock contention",
        description="DB connections exhausted",
        category="software",
        priority="CRITICAL",
        status="escalated",
        escalation_reason="Requires DB parameter tuning and connection pool expansion",
        reporter_id=seed_data["emp1"].account_id,
        assigned_to=seed_data["it1"].account_id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    # 1. IT_SUPPORT cannot update escalated ticket -> 403 Forbidden
    res_it = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "resolved", "resolution_note": "Fixed by IT"},
        headers=it1_headers,
    )
    assert res_it.status_code == 403
    assert "System Administrators" in res_it.json()["detail"]

    # 2. SysAdmin cannot transition escalated directly to closed -> 409 Conflict
    res_sys_closed = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "closed"},
        headers=sys_headers,
    )
    assert res_sys_closed.status_code == 409

    # 3. SysAdmin resolves escalated ticket -> 200 OK
    res_sys_resolve = client.put(
        f"/api/v1/support/tickets/{ticket.id}/status",
        json={"status": "resolved", "resolution_note": "Expanded RDS max_connections pool to 500."},
        headers=sys_headers,
    )
    assert res_sys_resolve.status_code == 200
    assert res_sys_resolve.json()["status"] == "resolved"

    # Both reporter and IT assignee should receive notification
    reporter_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["emp1"].account_id,
            Notification.type == "TICKET_RESOLVED",
        )
        .first()
    )
    assert reporter_notif is not None

    it_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["it1"].account_id,
            Notification.type == "TICKET_RESOLVED",
        )
        .first()
    )
    assert it_notif is not None


# =============================================================================
# 6. test_notes_hidden_from_reporter
# =============================================================================

def test_notes_hidden_from_reporter(client, db_session, seed_data):
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}
    emp1_headers = {"X-User-Id": str(seed_data["emp1"].account_id)}

    # Submit ticket by emp1
    res_submit = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Broken monitor", "description": "Display cable snapped"},
        headers=emp1_headers,
    )
    ticket_id = res_submit.json()["id"]

    # IT Support adds internal troubleshooting note
    secret_note = "User had plugged DP cable into HDMI port using improper adapter. Replacing adapter."
    res_note = client.post(
        f"/api/v1/support/tickets/{ticket_id}/notes",
        json={"note": secret_note},
        headers=it1_headers,
    )
    assert res_note.status_code == 200

    # IT Support views ticket: note is visible
    res_it_view = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=it1_headers)
    assert res_it_view.status_code == 200
    it_acts = res_it_view.json()["activities"]
    note_act_it = next(a for a in it_acts if a["action"] == "NOTE_ADDED")
    assert note_act_it["note"] == secret_note

    # Reporter views ticket: note is hidden (None)
    res_emp_view = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=emp1_headers)
    assert res_emp_view.status_code == 200
    emp_acts = res_emp_view.json()["activities"]
    note_act_emp = next(a for a in emp_acts if a["action"] == "NOTE_ADDED")
    assert note_act_emp["note"] is None


# =============================================================================
# 7. test_notifications_on_create_assign_resolve
# =============================================================================

def test_notifications_on_create_assign_resolve(client, db_session, seed_data):
    emp1_headers = {"X-User-Id": str(seed_data["emp1"].account_id)}
    it1_headers = {"X-User-Id": str(seed_data["it1"].account_id)}

    # 1. On ticket creation: all active IT_SUPPORT users receive TICKET_CREATED
    res = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Cannot connect to Wi-Fi", "description": "Auth error on corporate SSID"},
        headers=emp1_headers,
    )
    assert res.status_code == 201
    ticket_id = res.json()["id"]

    it1_created_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["it1"].account_id,
            Notification.type == "TICKET_CREATED",
        )
        .first()
    )
    it2_created_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["it2"].account_id,
            Notification.type == "TICKET_CREATED",
        )
        .first()
    )
    assert it1_created_notif is not None
    assert it2_created_notif is not None

    # 2. On ticket assign: assignee receives TICKET_ASSIGNED
    res_assign = client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={"assignee_account_id": str(seed_data["it2"].account_id)},
        headers=it1_headers,
    )
    assert res_assign.status_code == 200

    assigned_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["it2"].account_id,
            Notification.type == "TICKET_ASSIGNED",
        )
        .first()
    )
    assert assigned_notif is not None

    # 3. On ticket resolve: reporter receives TICKET_RESOLVED
    res_resolve = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "resolved", "resolution_note": "Re-provisioned radius 802.1X certificate."},
        headers=it1_headers,
    )
    assert res_resolve.status_code == 200

    resolved_notif = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == seed_data["emp1"].account_id,
            Notification.type == "TICKET_RESOLVED",
        )
        .first()
    )
    assert resolved_notif is not None
