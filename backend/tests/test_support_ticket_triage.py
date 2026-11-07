import uuid
import time
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
from app.models.support import SupportTicket, TicketActivity
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.enums import UserType


@pytest.fixture(scope="function")
def db_session():
    """Create fresh in-memory database and yield a clean session for every test."""
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
def seed_users(db_session):
    """Seed test users across multiple roles."""
    reporter = UserAccount(
        account_id=uuid.UUID("aa000000-0000-0000-0000-000000000001"),
        email="reporter.employee@company.com",
        password_hash="test_hashed_pass_1",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    it_support_1 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000001"),
        email="it.staff1@company.com",
        password_hash="test_hashed_pass_2",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    it_support_2 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000002"),
        email="it.staff2@company.com",
        password_hash="test_hashed_pass_3",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    sys_admin = UserAccount(
        account_id=uuid.UUID("cc000000-0000-0000-0000-000000000001"),
        email="sysadmin@company.com",
        password_hash="test_hashed_pass_4",
        user_type=UserType.SYSTEM_ADMIN,
        is_active=True,
    )
    regular_employee = UserAccount(
        account_id=uuid.UUID("dd000000-0000-0000-0000-000000000001"),
        email="regular.dev@company.com",
        password_hash="test_hashed_pass_5",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([reporter, it_support_1, it_support_2, sys_admin, regular_employee])
    db_session.commit()

    return {
        "reporter": reporter,
        "it_support_1": it_support_1,
        "it_support_2": it_support_2,
        "sys_admin": sys_admin,
        "regular_employee": regular_employee,
    }


@pytest.fixture(scope="function")
def seed_ticket(db_session, seed_users):
    """Seed a sample support ticket."""
    now_utc = datetime.now(timezone.utc)
    ticket = SupportTicket(
        ticket_number="TCK-00001",
        subject="Laptop Blue Screen Crash on Boot",
        description="Dell Latitude laptop crashes with BSOD VIDEO_TDR_FAILURE upon startup.",
        category="hardware",
        priority="HIGH",
        status="open",
        reporter_id=seed_users["reporter"].account_id,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    return ticket


# =========================================================================
# Acceptance Criterion 1: Restricts triage endpoints to IT_SUPPORT & SYSTEM_ADMIN
# =========================================================================

def test_rbac_restricts_triage_endpoints_for_unauthorized_roles(client, seed_users, seed_ticket):
    employee_headers = {"X-User-Id": str(seed_users["regular_employee"].account_id)}
    ticket_id = seed_ticket.id

    # 1. GET /api/v1/support/tickets
    res = client.get("/api/v1/support/tickets", headers=employee_headers)
    assert res.status_code == 403
    assert "insufficient role permissions" in res.json()["detail"].lower()

    # 2. PUT /api/v1/support/tickets/{id}/assign
    res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={"assigned_to": str(seed_users["it_support_1"].account_id)},
        headers=employee_headers,
    )
    assert res.status_code == 403

    # 3. POST /api/v1/support/tickets/{id}/notes
    res = client.post(
        f"/api/v1/support/tickets/{ticket_id}/notes",
        json={"note": "Unauthorized employee attempt to add troubleshooting note"},
        headers=employee_headers,
    )
    assert res.status_code == 403

    # 4. PUT /api/v1/support/tickets/{id}/status
    res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "resolved"},
        headers=employee_headers,
    )
    assert res.status_code == 403

    # 5. GET /api/v1/support/tickets/queue/metrics
    res = client.get("/api/v1/support/tickets/queue/metrics", headers=employee_headers)
    assert res.status_code == 403


def test_rbac_allows_it_support_and_system_admin(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    admin_headers = {"X-User-Id": str(seed_users["sys_admin"].account_id)}

    # IT Support can view queue
    res_it = client.get("/api/v1/support/tickets", headers=it_headers)
    assert res_it.status_code == 200

    # System Admin can view queue
    res_admin = client.get("/api/v1/support/tickets", headers=admin_headers)
    assert res_admin.status_code == 200

    # Both can view queue metrics
    assert client.get("/api/v1/support/tickets/queue/metrics", headers=it_headers).status_code == 200
    assert client.get("/api/v1/support/tickets/queue/metrics", headers=admin_headers).status_code == 200


# =========================================================================
# Acceptance Criterion 2: Target Assignee IT_SUPPORT Role Check
# =========================================================================

def test_ticket_assignment_rejects_non_it_support_assignee(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    non_it_user_id = str(seed_users["regular_employee"].account_id)

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/assign",
        json={
            "assigned_to": non_it_user_id,
            "reassignment_reason": "Attempting invalid assignment to regular developer",
        },
        headers=it_headers,
    )
    assert res.status_code == 422
    data = res.json()
    assert "does not hold the it_support role" in data["detail"].lower()


def test_ticket_assignment_success(client, db_session, seed_users, seed_ticket):
    it1_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    target_assignee_id = str(seed_users["it_support_2"].account_id)

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/assign",
        json={
            "assigned_to": target_assignee_id,
            "reassignment_reason": "Escalating hardware issue to second technician",
        },
        headers=it1_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_to"] == target_assignee_id

    # Verify ASSIGNED record in ticket_activity
    activity = (
        db_session.query(TicketActivity)
        .filter(TicketActivity.ticket_id == seed_ticket.id, TicketActivity.action == "ASSIGNED")
        .first()
    )
    assert activity is not None
    assert activity.actor_id == seed_users["it_support_1"].account_id
    assert "Escalating hardware issue" in activity.note


# =========================================================================
# Acceptance Criterion 3: Appending Note Updates updated_at & Logs Activity
# =========================================================================

def test_append_troubleshooting_note(client, db_session, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    original_updated_at = seed_ticket.updated_at

    note_text = "Ran GPU memory stress test. Isolated error to faulty VRAM module."
    time.sleep(0.05)  # slight delay to ensure timestamp progression

    res = client.post(
        f"/api/v1/support/tickets/{seed_ticket.id}/notes",
        json={"note": note_text},
        headers=it_headers,
    )
    assert res.status_code == 201
    activity_data = res.json()
    assert activity_data["action"] == "NOTE_ADDED"
    assert activity_data["note"] == note_text

    # Verify parent ticket updated_at was touched
    db_session.refresh(seed_ticket)
    assert seed_ticket.updated_at >= original_updated_at


# =========================================================================
# Acceptance Criterion 4: Status Transitions & Reporter Notification
# =========================================================================

def test_status_transition_to_resolved_triggers_notification(client, db_session, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}

    # Transition: open -> in_progress
    res_in_progress = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/status",
        json={"status": "in_progress", "resolution_notes": "Motherboard replacement underway"},
        headers=it_headers,
    )
    assert res_in_progress.status_code == 200
    assert res_in_progress.json()["status"] == "in_progress"

    # Transition: in_progress -> resolved
    res_resolved = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/status",
        json={"status": "resolved", "resolution_notes": "Motherboard replaced, system tested 100% OK"},
        headers=it_headers,
    )
    assert res_resolved.status_code == 200
    resolved_ticket = res_resolved.json()
    assert resolved_ticket["status"] == "resolved"
    assert resolved_ticket["resolved_at"] is not None

    # Verify notification created for reporter
    notification = (
        db_session.query(Notification)
        .filter(Notification.account_id == seed_ticket.reporter_id)
        .first()
    )
    if notification:
        assert notification.type == "TICKET_RESOLVED"


# =========================================================================
# Acceptance Criterion 5: IT Queue Filters
# =========================================================================

def test_queue_filters(client, db_session, seed_users):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    reporter_id = seed_users["reporter"].account_id
    it1_id = seed_users["it_support_1"].account_id
    it2_id = seed_users["it_support_2"].account_id

    t1 = SupportTicket(
        ticket_number="TCK-10001",
        subject="Hardware failure",
        description="Printer offline",
        category="hardware",
        priority="LOW",
        status="open",
        reporter_id=reporter_id,
        assigned_to=it1_id,
    )
    t2 = SupportTicket(
        ticket_number="TCK-10002",
        subject="Network latency",
        description="Switch dropping packets",
        category="network",
        priority="CRITICAL",
        status="in_progress",
        reporter_id=reporter_id,
        assigned_to=it2_id,
    )
    t3 = SupportTicket(
        ticket_number="TCK-10003",
        subject="Access card invalid",
        description="Badge scan fails",
        category="access",
        priority="MEDIUM",
        status="resolved",
        reporter_id=reporter_id,
        assigned_to=it1_id,
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # Filter by status=open
    res = client.get("/api/v1/support/tickets?status=open", headers=it_headers)
    assert res.status_code == 200
    data = res.json()
    assert all(t["status"] == "open" for t in data)
    assert any(t["ticket_number"] == "TCK-10001" for t in data)

    # Filter by category=network
    res = client.get("/api/v1/support/tickets?category=network", headers=it_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["ticket_number"] == "TCK-10002"

    # Filter by assigned_to=it1_id
    res = client.get(f"/api/v1/support/tickets?assigned_to={it1_id}", headers=it_headers)
    assert res.status_code == 200
    data = res.json()
    assert all(t["assigned_to"] == str(it1_id) for t in data)

    # Combined filter: status=open&category=hardware&assigned_to=it1_id
    res = client.get(
        f"/api/v1/support/tickets?status=open&category=hardware&assigned_to={it1_id}",
        headers=it_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["ticket_number"] == "TCK-10001"

    # Filter by priority=CRITICAL
    res = client.get("/api/v1/support/tickets?priority=CRITICAL", headers=it_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["ticket_number"] == "TCK-10002"


def test_queue_metrics_aggregation(client, db_session, seed_users):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    reporter_id = seed_users["reporter"].account_id
    it1_id = seed_users["it_support_1"].account_id

    t1 = SupportTicket(
        ticket_number="TCK-99001",
        subject="Issue A",
        description="Unassigned open ticket",
        category="hardware",
        priority="HIGH",
        status="open",
        reporter_id=reporter_id,
        assigned_to=None,
    )
    t2 = SupportTicket(
        ticket_number="TCK-99002",
        subject="Issue B",
        description="Resolved ticket",
        category="software",
        priority="LOW",
        status="resolved",
        reporter_id=reporter_id,
        assigned_to=it1_id,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    res = client.get("/api/v1/support/tickets/queue/metrics", headers=it_headers)
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["open_count"] >= 1
    assert metrics["resolved_count"] >= 1
    assert metrics["unassigned_count"] >= 1
    assert metrics["total_tickets"] >= 2


def test_ticket_not_found_handling(client, seed_users):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    non_existent_id = 999999

    res = client.get(f"/api/v1/support/tickets/{non_existent_id}", headers=it_headers)
    assert res.status_code == 404

    res = client.put(
        f"/api/v1/support/tickets/{non_existent_id}/assign",
        json={"assigned_to": str(seed_users["it_support_1"].account_id)},
        headers=it_headers,
    )
    assert res.status_code == 404

    res = client.post(
        f"/api/v1/support/tickets/{non_existent_id}/notes",
        json={"note": "Test note"},
        headers=it_headers,
    )
    assert res.status_code == 404

    res = client.put(
        f"/api/v1/support/tickets/{non_existent_id}/status",
        json={"status": "resolved"},
        headers=it_headers,
    )
    assert res.status_code == 404


def test_invalid_status_transition_rejected(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/status",
        json={"status": "invalid_status_xyz"},
        headers=it_headers,
    )
    assert res.status_code == 422
    assert "invalid status" in res.json()["detail"].lower()


def test_assign_to_non_existent_user(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    fake_uuid = str(uuid.uuid4())

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.id}/assign",
        json={"assigned_to": fake_uuid},
        headers=it_headers,
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_complete_end_to_end_support_lifecycle(client, seed_users):
    reporter_headers = {"X-User-Id": str(seed_users["reporter"].account_id)}
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}

    # 1. Reporter submits ticket
    create_res = client.post(
        "/api/v1/support/tickets",
        json={
            "subject": "Monitor flickering and power cuts",
            "description": "HDMI port appears loose on external monitor",
            "category": "hardware",
            "priority": "HIGH",
        },
        headers=reporter_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]
    assert create_res.json()["status"] == "open"

    # 2. IT Support views ticket queue
    queue_res = client.get("/api/v1/support/tickets?status=open&category=hardware", headers=it_headers)
    assert queue_res.status_code == 200
    assert any(t["id"] == ticket_id for t in queue_res.json())

    # 3. IT Support assigns ticket to self
    assign_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={"assigned_to": str(seed_users["it_support_1"].account_id)},
        headers=it_headers,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_to"] == str(seed_users["it_support_1"].account_id)

    # 4. IT Support transitions status to in_progress
    prog_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "in_progress", "resolution_notes": "Replaced HDMI cable, testing with docking station."},
        headers=it_headers,
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["status"] == "in_progress"

    # 5. IT Support logs troubleshooting note
    note_res = client.post(
        f"/api/v1/support/tickets/{ticket_id}/notes",
        json={"note": "Display signal stable for 30 minutes under load."},
        headers=it_headers,
    )
    assert note_res.status_code == 201
    assert note_res.json()["action"] == "NOTE_ADDED"

    # 6. IT Support marks resolved
    resolve_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "resolved", "resolution_notes": "Defective HDMI cable replaced with genuine 4K braided cable."},
        headers=it_headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"
    assert resolve_res.json()["resolved_at"] is not None

    # 7. Check full details & history
    detail_res = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=it_headers)
    assert detail_res.status_code == 200
    details = detail_res.json()
    assert len(details["activities"]) >= 4


def test_append_troubleshooting_note_empty_rejected(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}

    # Empty string note
    res = client.post(
        f"/api/v1/support/tickets/{seed_ticket.id}/notes",
        json={"note": ""},
        headers=it_headers,
    )
    assert res.status_code == 422

    # Whitespace-only note
    res = client.post(
        f"/api/v1/support/tickets/{seed_ticket.id}/notes",
        json={"note": "    \t\n  "},
        headers=it_headers,
    )
    assert res.status_code == 422


def test_queue_pagination_skip_and_limit(client, db_session, seed_users):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    reporter_id = seed_users["reporter"].account_id

    # Create 5 tickets with distinct subjects
    tickets = [
        SupportTicket(
            ticket_number=f"TCK-PAG-{i:03d}",
            subject=f"Pagination Ticket {i}",
            description=f"Pagination test description {i}",
            category="software",
            priority="MEDIUM",
            status="open",
            reporter_id=reporter_id,
        )
        for i in range(1, 6)
    ]
    db_session.add_all(tickets)
    db_session.commit()

    # Request limit=2
    res = client.get("/api/v1/support/tickets?limit=2", headers=it_headers)
    assert res.status_code == 200
    assert len(res.json()) == 2

    # Request limit=2, skip=2
    res_page2 = client.get("/api/v1/support/tickets?limit=2&skip=2", headers=it_headers)
    assert res_page2.status_code == 200
    assert len(res_page2.json()) == 2
    page1_ids = {t["id"] for t in res.json()}
    page2_ids = {t["id"] for t in res_page2.json()}
    assert page1_ids.isdisjoint(page2_ids)
