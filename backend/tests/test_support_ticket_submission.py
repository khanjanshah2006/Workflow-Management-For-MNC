import uuid
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
from app.models.enums import UserType


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database and yield session."""
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
    """Seed test users: two employees and one IT support staff."""
    emp1 = UserAccount(
        account_id=uuid.UUID("aa000000-0000-0000-0000-000000000001"),
        email="alice.employee@company.com",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp2 = UserAccount(
        account_id=uuid.UUID("aa000000-0000-0000-0000-000000000002"),
        email="bob.employee@company.com",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    it_support = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000001"),
        email="charlie.itsupport@company.com",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    db_session.add_all([emp1, emp2, it_support])
    db_session.commit()
    return {"emp1": emp1, "emp2": emp2, "it_support": it_support}


# =========================================================================
# Acceptance Criterion 1: Auto-increments human-readable ticket_number sequence
# =========================================================================

def test_ticket_number_auto_increment_sequence(client, seed_users):
    headers = {"X-User-Id": str(seed_users["emp1"].account_id)}

    res1 = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Mouse not working", "description": "Wireless mouse laser does not respond"},
        headers=headers,
    )
    assert res1.status_code == 201
    assert res1.json()["ticket_number"] == "TKT-001"

    res2 = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Keyboard key stuck", "description": "Spacebar is mechanically stuck"},
        headers=headers,
    )
    assert res2.status_code == 201
    assert res2.json()["ticket_number"] == "TKT-002"

    res3 = client.post(
        "/api/v1/support/tickets",
        json={"subject": "VPN login failure", "description": "Cannot connect to internal network"},
        headers=headers,
    )
    assert res3.status_code == 201
    assert res3.json()["ticket_number"] == "TKT-003"


# =========================================================================
# Acceptance Criterion 2: Creating ticket auto-creates initial CREATED activity
# =========================================================================

def test_create_ticket_creates_initial_activity(client, db_session, seed_users):
    emp1_id = seed_users["emp1"].account_id
    headers = {"X-User-Id": str(emp1_id)}

    res = client.post(
        "/api/v1/support/tickets",
        json={
            "subject": "Dual monitor HDMI adapter needed",
            "description": "Need second display adapter for productivity",
            "category": "hardware",
            "priority": "LOW",
        },
        headers=headers,
    )
    assert res.status_code == 201
    ticket_data = res.json()
    ticket_id = ticket_data["id"]

    # Verify ticket_activity entry in database
    activity = db_session.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket_id
    ).first()

    assert activity is not None, "Initial ticket_activity record was not created!"
    assert activity.action == "CREATED"
    assert activity.activity_type == "CREATED"
    assert activity.actor_id == emp1_id
    assert activity.performed_by == emp1_id
    assert "submitted by reporter" in activity.note.lower()


# =========================================================================
# Acceptance Criterion 3: Ordinary employees cannot see other employees' tickets
# =========================================================================

def test_ordinary_employee_cannot_see_other_employee_ticket(client, seed_users):
    emp1_headers = {"X-User-Id": str(seed_users["emp1"].account_id)}
    emp2_headers = {"X-User-Id": str(seed_users["emp2"].account_id)}
    it_headers = {"X-User-Id": str(seed_users["it_support"].account_id)}

    # Alice creates a ticket
    create_res = client.post(
        "/api/v1/support/tickets",
        json={
            "subject": "Alice Confidential Issue",
            "description": "Private ticket regarding Alice's laptop",
        },
        headers=emp1_headers,
    )
    ticket_id = create_res.json()["id"]

    # Alice CAN see her own ticket
    alice_res = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=emp1_headers)
    assert alice_res.status_code == 200
    assert alice_res.json()["id"] == ticket_id

    # Bob (ordinary employee) CANNOT see Alice's ticket -> 403 Forbidden
    bob_res = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=emp2_headers)
    assert bob_res.status_code == 403
    assert "cannot view other employees" in bob_res.json()["detail"].lower()

    # IT Support CAN see Alice's ticket
    it_res = client.get(f"/api/v1/support/tickets/{ticket_id}", headers=it_headers)
    assert it_res.status_code == 200
    assert it_res.json()["id"] == ticket_id


# =========================================================================
# GET /api/v1/support/tickets/my - Employee ticket history inspection
# =========================================================================

def test_get_my_tickets_isolation(client, seed_users):
    emp1_headers = {"X-User-Id": str(seed_users["emp1"].account_id)}
    emp2_headers = {"X-User-Id": str(seed_users["emp2"].account_id)}

    # Alice creates 2 tickets
    client.post(
        "/api/v1/support/tickets",
        json={"subject": "Alice Issue 1", "description": "Description 1"},
        headers=emp1_headers,
    )
    client.post(
        "/api/v1/support/tickets",
        json={"subject": "Alice Issue 2", "description": "Description 2"},
        headers=emp1_headers,
    )

    # Bob creates 1 ticket
    client.post(
        "/api/v1/support/tickets",
        json={"subject": "Bob Issue 1", "description": "Description 3"},
        headers=emp2_headers,
    )

    # Alice calls /my
    alice_my = client.get("/api/v1/support/tickets/my", headers=emp1_headers)
    assert alice_my.status_code == 200
    alice_tickets = alice_my.json()
    assert len(alice_tickets) == 2
    assert all(t["reporter_id"] == str(seed_users["emp1"].account_id) for t in alice_tickets)
    assert all("Alice" in t["subject"] for t in alice_tickets)

    # Bob calls /my
    bob_my = client.get("/api/v1/support/tickets/my", headers=emp2_headers)
    assert bob_my.status_code == 200
    bob_tickets = bob_my.json()
    assert len(bob_tickets) == 1
    assert bob_tickets[0]["reporter_id"] == str(seed_users["emp2"].account_id)
    assert "Bob" in bob_tickets[0]["subject"]
