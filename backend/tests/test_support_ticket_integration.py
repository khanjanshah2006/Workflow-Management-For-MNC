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
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.enums import UserType, TicketStatus, TicketActivityType


@pytest.fixture(scope="function")
def db_session():
    """Create fresh in-memory database and yield a clean session."""
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
    """Seed test users for integration tests."""
    reporter = UserAccount(
        account_id=uuid.UUID("aa000000-0000-0000-0000-000000000001"),
        email="reporter@company.com",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    it_agent_1 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000001"),
        email="agent1@support.internal",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    it_agent_2 = UserAccount(
        account_id=uuid.UUID("bb000000-0000-0000-0000-000000000002"),
        email="agent2@support.internal",
        user_type=UserType.IT_SUPPORT,
        is_active=True,
    )
    db_session.add_all([reporter, it_agent_1, it_agent_2])
    db_session.commit()
    return {"reporter": reporter, "it_agent_1": it_agent_1, "it_agent_2": it_agent_2}


def test_it_staff_queue_workflow(client, seed_users):
    reporter_headers = {"X-User-Id": str(seed_users["reporter"].account_id)}
    it_headers = {"X-User-Id": str(seed_users["it_agent_1"].account_id)}

    # 1. Reporter creates a ticket
    create_res = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Database latency spike", "description": "High read latency on Postgres connection pool"},
        headers=reporter_headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # 2. IT staff checks queue metrics
    metrics_res = client.get("/api/v1/support/tickets/queue/metrics", headers=it_headers)
    assert metrics_res.status_code == 200
    assert metrics_res.json()["open_count"] >= 1

    # 3. IT staff assigns ticket
    assign_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={"assigned_to": str(seed_users["it_agent_1"].account_id), "reassignment_reason": "Claiming ticket for root cause analysis"},
        headers=it_headers,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_to"] == str(seed_users["it_agent_1"].account_id)

    # 4. IT staff updates status to in_progress
    status_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "in_progress", "resolution_notes": "Identified slow queries, optimizing table indexes."},
        headers=it_headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "in_progress"

    # 5. IT staff adds troubleshooting note
    note_res = client.post(
        f"/api/v1/support/tickets/{ticket_id}/notes",
        json={"note": "Added composite index on ticket_number and category. Latency dropped to 12ms."},
        headers=it_headers,
    )
    assert note_res.status_code == 201

    # 6. IT staff marks resolved
    resolve_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "resolved", "resolution_notes": "Query performance restored within acceptable SLA."},
        headers=it_headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"


def test_reassignment_flow_between_it_agents(client, seed_users):
    reporter_headers = {"X-User-Id": str(seed_users["reporter"].account_id)}
    it1_headers = {"X-User-Id": str(seed_users["it_agent_1"].account_id)}

    # Create ticket
    create_res = client.post(
        "/api/v1/support/tickets",
        json={"subject": "Wi-Fi Access Point Offline", "description": "AP on Floor 3 is not broadcasting SSID"},
        headers=reporter_headers,
    )
    ticket_id = create_res.json()["id"]

    # Assign to Agent 1
    client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={"assigned_to": str(seed_users["it_agent_1"].account_id)},
        headers=it1_headers,
    )

    # Reassign to Agent 2
    reassign_res = client.put(
        f"/api/v1/support/tickets/{ticket_id}/assign",
        json={
            "assigned_to": str(seed_users["it_agent_2"].account_id),
            "reassignment_reason": "Escalating to network infrastructure specialist",
        },
        headers=it1_headers,
    )
    assert reassign_res.status_code == 200
    assert reassign_res.json()["assigned_to"] == str(seed_users["it_agent_2"].account_id)
