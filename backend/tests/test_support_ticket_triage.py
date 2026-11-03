import uuid
import time
from datetime import datetime, timezone
import pytest
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
from app.models.user_account import UserAccount
from app.models.support import SupportTicket, TicketActivity
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.enums import UserType, TicketStatus, TicketActivityType

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
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_users(db_session):
    """Seed test users across multiple roles."""
    reporter = UserAccount(
        account_id=uuid.UUID("aa000000-0000-0000-0000-000000000001"),
        email="reporter.employee@company.com",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    it_support_1 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000001"),
        email="it.staff1@company.com",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    it_support_2 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000002"),
        email="it.staff2@company.com",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    sys_admin = UserAccount(
        account_id=uuid.UUID("cc000000-0000-0000-0000-000000000001"),
        email="sysadmin@company.com",
        user_type=UserType.SYSTEM_ADMIN,
        is_active=True,
    )
    regular_employee = UserAccount(
        account_id=uuid.UUID("dd000000-0000-0000-0000-000000000001"),
        email="regular.dev@company.com",
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
        title="Laptop Blue Screen Crash on Boot",
        description="Dell Latitude laptop crashes with BSOD VIDEO_TDR_FAILURE upon startup.",
        category="hardware",
        priority="HIGH",
        status=TicketStatus.OPEN.value,
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
    ticket_id = seed_ticket.ticket_id

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
        json={"note": "Unauthorized note"},
        headers=employee_headers,
    )
    assert res.status_code == 403

    # 4. PUT /api/v1/support/tickets/{id}/status
    res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "in_progress"},
        headers=employee_headers,
    )
    assert res.status_code == 403


def test_rbac_allows_it_support_and_system_admin(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    admin_headers = {"X-User-Id": str(seed_users["sys_admin"].account_id)}

    # IT Support can access queue
    res_it = client.get("/api/v1/support/tickets", headers=it_headers)
    assert res_it.status_code == 200
    assert len(res_it.json()) >= 1

    # System Admin can access queue
    res_admin = client.get("/api/v1/support/tickets", headers=admin_headers)
    assert res_admin.status_code == 200
    assert len(res_admin.json()) >= 1


# =========================================================================
# Acceptance Criterion 2: Ticket assignment checks assignee holds IT_SUPPORT role
# =========================================================================

def test_ticket_assignment_rejects_non_it_support_assignee(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    non_it_user = seed_users["regular_employee"]

    # Try assigning to regular employee
    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.ticket_id}/assign",
        json={"assigned_to": str(non_it_user.account_id)},
        headers=it_headers,
    )
    assert res.status_code == 422
    assert "does not hold the it_support role" in res.json()["detail"].lower()


def test_ticket_assignment_success(client, db_session, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    target_assignee = seed_users["it_support_2"]

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.ticket_id}/assign",
        json={"assigned_to": str(target_assignee.account_id)},
        headers=it_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["assigned_to"] == str(target_assignee.account_id)

    # Verify activity was logged in database
    activity = db_session.query(TicketActivity).filter(
        TicketActivity.ticket_id == seed_ticket.ticket_id,
        TicketActivity.activity_type == TicketActivityType.ASSIGNED.value,
    ).first()
    assert activity is not None
    assert str(target_assignee.email) in activity.note

    # Verify audit log was recorded
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_name == "SUPPORT_TICKET",
        AuditLog.entity_ref_id == str(seed_ticket.ticket_id),
    ).first()
    assert audit is not None


# =========================================================================
# Acceptance Criterion 3: Appending note updates updated_at and creates NOTE_ADDED activity
# =========================================================================

def test_append_troubleshooting_note(client, db_session, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    ticket_id = seed_ticket.ticket_id
    initial_updated_at = seed_ticket.updated_at

    # Small sleep to ensure updated_at timestamp advances
    time.sleep(0.05)

    note_text = "Ran hardware diagnostics test: Passed memory check, GPU driver update needed."
    res = client.post(
        f"/api/v1/support/tickets/{ticket_id}/notes",
        json={"note": note_text},
        headers=it_headers,
    )
    assert res.status_code == 201
    activity_data = res.json()
    assert activity_data["activity_type"] == "NOTE_ADDED"
    assert activity_data["note"] == note_text
    assert activity_data["ticket_id"] == ticket_id

    # Refresh ticket from DB and verify updated_at was modified
    db_session.refresh(seed_ticket)
    assert seed_ticket.updated_at >= initial_updated_at

    # Verify activity in DB
    db_activity = db_session.query(TicketActivity).filter(
        TicketActivity.activity_id == activity_data["activity_id"]
    ).first()
    assert db_activity is not None
    assert db_activity.activity_type == "NOTE_ADDED"
    assert db_activity.performed_by == seed_users["it_support_1"].account_id


# =========================================================================
# Acceptance Criterion 4: Marking resolved notifies reporter via Person 1's notification service
# =========================================================================

def test_status_transition_to_resolved_triggers_notification(client, db_session, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    ticket_id = seed_ticket.ticket_id

    # 1. Transition open -> in_progress
    res_in_progress = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "in_progress", "resolution_notes": "Started investigating BSOD"},
        headers=it_headers,
    )
    assert res_in_progress.status_code == 200
    assert res_in_progress.json()["status"] == "in_progress"

    # 2. Transition in_progress -> resolved
    res_resolved = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "resolved", "resolution_notes": "Updated NVIDIA GPU drivers to version 535.12. Issue fixed."},
        headers=it_headers,
    )
    assert res_resolved.status_code == 200
    resolved_data = res_resolved.json()
    assert resolved_data["status"] == "resolved"
    assert resolved_data["resolved_at"] is not None

    # 3. Verify notification created for ticket reporter in DB
    reporter_id = seed_users["reporter"].account_id
    notification = db_session.query(Notification).filter(
        Notification.account_id == reporter_id,
        Notification.type == "TICKET_RESOLVED",
    ).first()

    assert notification is not None, "Notification was not created for reporter!"
    assert "Resolved" in notification.title
    assert seed_ticket.ticket_number in notification.title or seed_ticket.ticket_number in notification.message
    assert notification.is_read is False

    # 4. Verify STATUS_CHANGED activity recorded
    activity = db_session.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket_id,
        TicketActivity.activity_type == "STATUS_CHANGED",
        TicketActivity.new_status == "resolved",
    ).first()
    assert activity is not None
    assert activity.old_status == "in_progress"


# =========================================================================
# Query filters: ?status=open&category=hardware&assigned_to=uuid
# =========================================================================

def test_queue_filters(client, db_session, seed_users):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    reporter_id = seed_users["reporter"].account_id
    it1_id = seed_users["it_support_1"].account_id
    it2_id = seed_users["it_support_2"].account_id

    # Create 3 tickets with different attributes
    t1 = SupportTicket(
        ticket_number="TCK-10001",
        title="Laptop Screen Glitch",
        description="Flickering screen on external monitor",
        category="hardware",
        priority="HIGH",
        status="open",
        reporter_id=reporter_id,
        assigned_to=it1_id,
    )
    t2 = SupportTicket(
        ticket_number="TCK-10002",
        title="VPN Connection Failure",
        description="Cannot connect to corporate VPN from home",
        category="network",
        priority="CRITICAL",
        status="in_progress",
        reporter_id=reporter_id,
        assigned_to=it2_id,
    )
    t3 = SupportTicket(
        ticket_number="TCK-10003",
        title="Docker Desktop License Expired",
        description="Please renew Docker Desktop license",
        category="software",
        priority="LOW",
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

    # Create 2 tickets: 1 open unassigned, 1 resolved assigned
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


# =========================================================================
# Additional Edge Cases & End-to-End Lifecycle Verification
# =========================================================================

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
        f"/api/v1/support/tickets/{seed_ticket.ticket_id}/status",
        json={"status": "invalid_status_xyz"},
        headers=it_headers,
    )
    assert res.status_code == 422
    assert "invalid status" in res.json()["detail"].lower()


def test_assign_to_non_existent_user(client, seed_users, seed_ticket):
    it_headers = {"X-User-Id": str(seed_users["it_support_1"].account_id)}
    fake_uuid = str(uuid.uuid4())

    res = client.put(
        f"/api/v1/support/tickets/{seed_ticket.ticket_id}/assign",
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
            "title": "Monitor flickering and power cuts",
            "description": "HDMI port appears loose on external monitor",
            "category": "hardware",
            "priority": "HIGH",
        },
        headers=reporter_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["ticket_id"]
    assert create_res.json()["status"] == "open"

    # 2. IT Support views ticket queue
    queue_res = client.get("/api/v1/support/tickets?status=open&category=hardware", headers=it_headers)
    assert queue_res.status_code == 200
    assert any(t["ticket_id"] == ticket_id for t in queue_res.json())

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
    assert note_res.json()["activity_type"] == "NOTE_ADDED"

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
    assert len(details["activities"]) >= 4  # CREATED, ASSIGNED, STATUS_CHANGED, NOTE_ADDED, STATUS_CHANGED

