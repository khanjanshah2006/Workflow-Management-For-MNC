"""
Tests for Deliverables & Client Signoff Feature (US-22).

Covers:
  - PM/Admin publishing deliverables (`POST /api/v1/projects/{project_id}/deliverables`)
  - Client/PM listing deliverables (`GET /api/v1/client/projects/{project_id}/deliverables`)
  - Client signoff & feedback (`POST /api/v1/client/deliverables/{id}/feedback`)
  - Status transitions (`SUBMITTED` -> `ACCEPTED` / `CHANGES_REQUESTED`)
  - Mandatory comments when requesting changes (`422`)
  - Rating validation 1-5 (`422` outside range)
  - PM notification (`DELIVERABLE_FEEDBACK`) & compliance audit logs (`APPROVE` / `UPDATE`)
  - Strict client & PM scoping (`403`/`404`) and internal employee redaction
"""

import uuid
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.client_portal.router import (
    project_deliverables_router,
    router as client_portal_router,
)
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.deliverable import Deliverable, DeliverableFeedback
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.user_account import UserAccount


# ==============================================================================
# Fixtures & In-Memory SQLite Setup
# ==============================================================================

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="module")
def TestSessionLocal(test_engine):
    return sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
    )


@pytest.fixture(scope="module")
def app(TestSessionLocal):
    _app = FastAPI()
    _app.include_router(client_portal_router)
    _app.include_router(project_deliverables_router)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    _app.dependency_overrides[get_db] = override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def seed_data(TestSessionLocal):
    db = TestSessionLocal()

    pm1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm1@internal.com",
        password_hash="pw",
        user_type=UserType.PM,
        is_active=True,
    )
    pm2_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm2@internal.com",
        password_hash="pw",
        user_type=UserType.PM,
        is_active=True,
    )
    admin_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="admin@internal.com",
        password_hash="pw",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    emp_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp@internal.com",
        password_hash="pw",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    client_a_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="clienta@acme.com",
        password_hash="pw",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    client_b_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="clientb@globex.com",
        password_hash="pw",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    db.add_all([pm1_acc, pm2_acc, admin_acc, emp_acc, client_a_acc, client_b_acc])
    db.flush()

    pm1_emp = Employee(
        account_id=pm1_acc.account_id,
        emp_code="EMP-PM1",
        full_name="PM One",
        email="pm1-emp@internal.com",
        designation="Project Manager",
        date_of_joining=date(2024, 1, 1),
    )
    pm1 = ProjectManager(
        account_id=pm1_acc.account_id,
        emp_code="PM-001",
        full_name="PM One",
        email="pm1@internal.com",
        date_of_joining=date(2024, 1, 1),
    )
    pm2 = ProjectManager(
        account_id=pm2_acc.account_id,
        emp_code="PM-002",
        full_name="PM Two",
        email="pm2@internal.com",
        date_of_joining=date(2024, 2, 1),
    )
    client_a = Client(
        account_id=client_a_acc.account_id,
        company_name="Acme Corp",
        contact_person="Alice A",
        email="contact@acme.com",
        status=CommonStatus.ACTIVE,
    )
    client_b = Client(
        account_id=client_b_acc.account_id,
        company_name="Globex Inc",
        contact_person="Bob B",
        email="contact@globex.com",
        status=CommonStatus.ACTIVE,
    )
    db.add_all([pm1_emp, pm1, pm2, client_a, client_b])
    db.flush()

    project_a = Project(
        client_id=client_a.client_id,
        pm_id=pm1.pm_id,
        project_code="PRJ-DELIV-01",
        name="Acme Cloud Migration",
        description="Cloud migration deliverables project",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    project_b = Project(
        client_id=client_b.client_id,
        pm_id=pm2.pm_id,
        project_code="PRJ-DELIV-02",
        name="Globex Security Audit",
        description="Security audit project",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 11, 30),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    db.add_all([project_a, project_b])
    db.flush()

    milestone_a = ProjectMilestone(
        project_id=project_a.project_id,
        title="Phase 1 Architecture",
        target_date=date(2026, 3, 1),
        status=MilestoneStatus.PENDING,
    )
    milestone_b = ProjectMilestone(
        project_id=project_b.project_id,
        title="Audit Report",
        target_date=date(2026, 4, 1),
        status=MilestoneStatus.PENDING,
    )
    db.add_all([milestone_a, milestone_b])
    db.commit()

    data = {
        "pm1_acc": pm1_acc,
        "pm2_acc": pm2_acc,
        "admin_acc": admin_acc,
        "emp_acc": emp_acc,
        "client_a_acc": client_a_acc,
        "client_b_acc": client_b_acc,
        "pm1": pm1,
        "pm2": pm2,
        "client_a": client_a,
        "client_b": client_b,
        "project_a": project_a,
        "project_b": project_b,
        "milestone_a": milestone_a,
        "milestone_b": milestone_b,
    }
    db.close()
    return data


def _as(app: FastAPI, user: UserAccount) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


# ==============================================================================
# 1. Publishing Deliverables (POST /api/v1/projects/{project_id}/deliverables)
# ==============================================================================

class TestPublishDeliverable:
    def test_assigned_pm_can_publish_deliverable(self, app, seed_data, TestSessionLocal):
        client = _as(app, seed_data["pm1_acc"])
        pid = seed_data["project_a"].project_id
        mid = seed_data["milestone_a"].id

        res = client.post(
            f"/api/v1/projects/{pid}/deliverables",
            json={
                "title": "System Architecture SOW",
                "description": "High-level architecture document for signoff.",
                "file_url": "https://storage.example.com/deliverables/arch-v1.pdf",
                "milestone_id": mid,
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["project_id"] == pid
        assert body["milestone_id"] == mid
        assert body["title"] == "System Architecture SOW"
        assert body["version"] == 1
        assert body["status"] == "SUBMITTED"
        assert "submitted_by" not in body

        # Audit log recorded for deliverable creation
        db = TestSessionLocal()
        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_name == "DELIVERABLE",
                AuditLog.entity_ref_id == str(body["deliverable_id"]),
                AuditLog.action == AuditAction.CREATE,
            )
            .first()
        )
        assert audit is not None
        db.close()

    def test_republish_auto_increments_version(self, app, seed_data):
        client = _as(app, seed_data["pm1_acc"])
        pid = seed_data["project_a"].project_id

        res = client.post(
            f"/api/v1/projects/{pid}/deliverables",
            json={
                "title": "System Architecture SOW",
                "file_url": "https://storage.example.com/deliverables/arch-v2.pdf",
            },
        )
        assert res.status_code == 201
        assert res.json()["version"] == 2

    def test_admin_can_publish_deliverable(self, app, seed_data):
        client = _as(app, seed_data["admin_acc"])
        pid = seed_data["project_b"].project_id

        res = client.post(
            f"/api/v1/projects/{pid}/deliverables",
            json={
                "title": "Initial Security Findings",
                "file_url": "https://storage.example.com/deliverables/sec-v1.pdf",
                "version": 1,
            },
        )
        assert res.status_code == 201
        assert res.json()["project_id"] == pid
        assert res.json()["status"] == "SUBMITTED"

    def test_unassigned_pm_forbidden(self, app, seed_data):
        client = _as(app, seed_data["pm2_acc"])
        pid_a = seed_data["project_a"].project_id

        res = client.post(
            f"/api/v1/projects/{pid_a}/deliverables",
            json={
                "title": "Unauthorized Deliverable",
                "file_url": "https://storage.example.com/unauth.pdf",
            },
        )
        assert res.status_code == 403

    def test_client_and_employee_cannot_publish(self, app, seed_data):
        pid = seed_data["project_a"].project_id
        payload = {
            "title": "Blocked Deliverable",
            "file_url": "https://storage.example.com/blocked.pdf",
        }
        for acc in (seed_data["client_a_acc"], seed_data["emp_acc"]):
            res = _as(app, acc).post(f"/api/v1/projects/{pid}/deliverables", json=payload)
            assert res.status_code == 403

    def test_mismatched_milestone_returns_404(self, app, seed_data):
        client = _as(app, seed_data["pm1_acc"])
        pid_a = seed_data["project_a"].project_id
        mid_b = seed_data["milestone_b"].id

        res = client.post(
            f"/api/v1/projects/{pid_a}/deliverables",
            json={
                "title": "Wrong Milestone",
                "file_url": "https://storage.example.com/wrong.pdf",
                "milestone_id": mid_b,
            },
        )
        assert res.status_code == 404


# ==============================================================================
# 2. Listing Deliverables (GET /api/v1/client/projects/{project_id}/deliverables)
# ==============================================================================

class TestListDeliverables:
    def test_client_lists_own_project_deliverables(self, app, seed_data):
        client = _as(app, seed_data["client_a_acc"])
        pid = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/deliverables")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 2
        for item in items:
            assert item["project_id"] == pid
            assert "submitted_by" not in item

    def test_assigned_pm_lists_project_deliverables(self, app, seed_data):
        client = _as(app, seed_data["pm1_acc"])
        pid = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/deliverables")
        assert res.status_code == 200
        assert len(res.json()) >= 2

    def test_cross_client_list_returns_404(self, app, seed_data):
        client = _as(app, seed_data["client_b_acc"])
        pid_a = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid_a}/deliverables")
        assert res.status_code == 404

    def test_unassigned_pm_list_returns_403(self, app, seed_data):
        client = _as(app, seed_data["pm2_acc"])
        pid_a = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid_a}/deliverables")
        assert res.status_code == 403

    def test_employee_list_returns_403(self, app, seed_data):
        client = _as(app, seed_data["emp_acc"])
        pid_a = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid_a}/deliverables")
        assert res.status_code == 403


# ==============================================================================
# 3. Client Signoff & Feedback (POST /api/v1/client/deliverables/{id}/feedback)
# ==============================================================================

class TestDeliverableFeedbackSignoff:
    def _create_deliverable(self, app, seed_data, title="API Spec Document") -> int:
        res = _as(app, seed_data["pm1_acc"]).post(
            f"/api/v1/projects/{seed_data['project_a'].project_id}/deliverables",
            json={
                "title": title,
                "file_url": "https://storage.example.com/spec.pdf",
            },
        )
        assert res.status_code == 201
        return res.json()["deliverable_id"]

    def test_accept_deliverable_notifies_pm_and_audits(self, app, seed_data, TestSessionLocal):
        did = self._create_deliverable(app, seed_data, title="Final Acceptance Doc")
        client = _as(app, seed_data["client_a_acc"])

        res = client.post(
            f"/api/v1/client/deliverables/{did}/feedback",
            json={
                "decision": "ACCEPTED",
                "comments": "Meets all functional requirements outlined in SOW.",
                "rating": 5,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ACCEPTED"
        assert len(body["feedbacks"]) == 1
        assert body["feedbacks"][0]["decision"] == "ACCEPTED"
        assert body["feedbacks"][0]["rating"] == 5

        db = TestSessionLocal()
        notif = (
            db.query(Notification)
            .filter(
                Notification.account_id == seed_data["pm1_acc"].account_id,
                Notification.type == "DELIVERABLE_FEEDBACK",
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert notif is not None
        assert "Final Acceptance Doc" in notif.title

        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_name == "DELIVERABLE",
                AuditLog.entity_ref_id == str(did),
                AuditLog.action == AuditAction.APPROVE,
            )
            .first()
        )
        assert audit is not None
        db.close()

    def test_request_changes_records_comments_and_audits(self, app, seed_data, TestSessionLocal):
        did = self._create_deliverable(app, seed_data, title="UI Wireframes")
        client = _as(app, seed_data["client_a_acc"])

        res = client.post(
            f"/api/v1/client/deliverables/{did}/feedback",
            json={
                "decision": "CHANGES_REQUESTED",
                "comments": "Please update dashboard contrast and export button label.",
                "rating": 3,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "CHANGES_REQUESTED"
        assert body["feedbacks"][0]["decision"] == "CHANGES_REQUESTED"
        assert "contrast" in body["feedbacks"][0]["comments"]

        db = TestSessionLocal()
        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_name == "DELIVERABLE",
                AuditLog.entity_ref_id == str(did),
                AuditLog.action == AuditAction.UPDATE,
            )
            .first()
        )
        assert audit is not None
        db.close()

    def test_request_changes_without_comments_returns_422(self, app, seed_data):
        did = self._create_deliverable(app, seed_data, title="Missing Comment Check")
        client = _as(app, seed_data["client_a_acc"])

        res1 = client.post(
            f"/api/v1/client/deliverables/{did}/feedback",
            json={"decision": "CHANGES_REQUESTED", "rating": 2},
        )
        assert res1.status_code == 422

        res2 = client.post(
            f"/api/v1/client/deliverables/{did}/feedback",
            json={"decision": "CHANGES_REQUESTED", "comments": "   ", "rating": 2},
        )
        assert res2.status_code == 422

    @pytest.mark.parametrize("bad_rating", [0, -1, 6, 100])
    def test_rating_outside_range_returns_422(self, app, seed_data, bad_rating):
        did = self._create_deliverable(app, seed_data, title=f"Rating Check {bad_rating}")
        client = _as(app, seed_data["client_a_acc"])

        res = client.post(
            f"/api/v1/client/deliverables/{did}/feedback",
            json={
                "decision": "ACCEPTED",
                "comments": "Testing rating bounds",
                "rating": bad_rating,
            },
        )
        assert res.status_code == 422

    def test_cross_client_feedback_returns_404(self, app, seed_data):
        did_a = self._create_deliverable(app, seed_data, title="Acme Only Deliverable")
        client_b = _as(app, seed_data["client_b_acc"])

        res = client_b.post(
            f"/api/v1/client/deliverables/{did_a}/feedback",
            json={"decision": "ACCEPTED", "comments": "Sneaky signoff", "rating": 5},
        )
        assert res.status_code == 404

    def test_nonexistent_deliverable_returns_404(self, app, seed_data):
        client = _as(app, seed_data["client_a_acc"])
        res = client.post(
            "/api/v1/client/deliverables/999999/feedback",
            json={"decision": "ACCEPTED", "comments": "Does not exist", "rating": 5},
        )
        assert res.status_code == 404

    def test_non_client_roles_cannot_submit_feedback(self, app, seed_data):
        did = self._create_deliverable(app, seed_data, title="Role Check Deliverable")
        payload = {"decision": "ACCEPTED", "comments": "Internal attempt", "rating": 5}
        for acc in (seed_data["pm1_acc"], seed_data["admin_acc"], seed_data["emp_acc"]):
            res = _as(app, acc).post(
                f"/api/v1/client/deliverables/{did}/feedback", json=payload
            )
            assert res.status_code == 403

    def test_unauthenticated_returns_401(self, app):
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        res = client.post(
            "/api/v1/client/deliverables/1/feedback",
            json={"decision": "ACCEPTED", "rating": 5},
        )
        assert res.status_code == 401
