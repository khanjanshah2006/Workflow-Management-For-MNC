"""
Tests for Client Portal Feature (US-20, US-21).

Covers:
  - RBAC enforcement (only CLIENT role allowed)
  - Strict project scoping (client A cannot see client B's projects)
  - Milestone completion percentage calculation
  - Milestone listing with ownership validation
  - 404 on cross-client project access (prevents ID enumeration)
  - Redaction check (no internal employee fields in response)
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.enums import (
    CommonStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    UserType,
)
from app.models.user_account import UserAccount
from app.models.client import Client
from app.models.project_manager import ProjectManager
from app.models.project import Project
from app.models.milestone import ProjectMilestone
from app.features.client_portal.router import router as client_portal_router


# ==============================================================================
# Test Fixtures & In-Memory SQLite Setup
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
    """Build a minimal FastAPI app with only the client portal router."""
    _app = FastAPI()
    _app.include_router(client_portal_router)

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
    """
    Seed the database with:
      - Two client user accounts (client_a, client_b)
      - A non-client user account (employee)
      - Corresponding Client profiles
      - A PM / employee for FK satisfaction
      - Two projects: one for client_a, one for client_b
      - Milestones on each project
    """
    db = TestSessionLocal()

    # --- User accounts ---
    client_a_account = UserAccount(
        account_id=uuid.UUID("aaaa0000-0000-0000-0000-000000000001"),
        email="clienta@acme.com",
        password_hash="hashed_pw_a",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    client_b_account = UserAccount(
        account_id=uuid.UUID("bbbb0000-0000-0000-0000-000000000002"),
        email="clientb@globex.com",
        password_hash="hashed_pw_b",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    employee_account = UserAccount(
        account_id=uuid.UUID("eeee0000-0000-0000-0000-000000000003"),
        email="emp@internal.com",
        password_hash="hashed_pw_e",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    admin_account = UserAccount(
        account_id=uuid.UUID("dddd0000-0000-0000-0000-000000000004"),
        email="admin@internal.com",
        password_hash="hashed_pw_d",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    pm_account = UserAccount(
        account_id=uuid.UUID("cccc0000-0000-0000-0000-000000000005"),
        email="pm@internal.com",
        password_hash="hashed_pw_pm",
        user_type=UserType.PM,
        is_active=True,
    )
    db.add_all([client_a_account, client_b_account, employee_account, admin_account, pm_account])
    db.flush()

    # --- PM record for FK ---
    pm = ProjectManager(
        account_id=pm_account.account_id,
        emp_code="PM-001",
        full_name="Project Manager",
        email="pm-profile@internal.com",
        phone="1234567890",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(pm)
    db.flush()

    # --- Client profiles ---
    client_a = Client(
        account_id=client_a_account.account_id,
        company_name="Acme Corp",
        contact_person="Alice A",
        email="contact@acme.com",
        status=CommonStatus.ACTIVE,
    )
    client_b = Client(
        account_id=client_b_account.account_id,
        company_name="Globex Inc",
        contact_person="Bob B",
        email="contact@globex.com",
        status=CommonStatus.ACTIVE,
    )
    db.add_all([client_a, client_b])
    db.flush()

    # --- Projects ---
    project_a = Project(
        client_id=client_a.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-ACME-001",
        name="Acme Website Redesign",
        description="Full redesign of the corporate website",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    project_b = Project(
        client_id=client_b.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-GLX-001",
        name="Globex ERP Migration",
        description="Migrate legacy ERP to cloud",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 12, 31),
        priority=PriorityLevel.CRITICAL,
        status=ProjectStatus.ACTIVE,
    )
    # A second project for client A with NO milestones (0% completion)
    project_a2 = Project(
        client_id=client_a.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-ACME-002",
        name="Acme Mobile App",
        description="New mobile app",
        start_date=date(2026, 7, 1),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.PLANNED,
    )
    db.add_all([project_a, project_b, project_a2])
    db.flush()

    # --- Milestones for project_a: 2 completed, 2 pending → 50% ---
    milestones_a = [
        ProjectMilestone(
            project_id=project_a.project_id,
            title="Design Mockups",
            target_date=date(2026, 2, 1),
            status=MilestoneStatus.COMPLETED,
            completed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
        ProjectMilestone(
            project_id=project_a.project_id,
            title="Frontend Build",
            target_date=date(2026, 3, 15),
            status=MilestoneStatus.COMPLETED,
            completed_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        ),
        ProjectMilestone(
            project_id=project_a.project_id,
            title="Backend Integration",
            target_date=date(2026, 4, 30),
            status=MilestoneStatus.PENDING,
        ),
        ProjectMilestone(
            project_id=project_a.project_id,
            title="UAT & Launch",
            target_date=date(2026, 6, 15),
            status=MilestoneStatus.PENDING,
        ),
        # Soft-deleted milestone — must NOT be counted
        ProjectMilestone(
            project_id=project_a.project_id,
            title="Deleted Phase",
            target_date=date(2026, 5, 1),
            status=MilestoneStatus.PENDING,
            is_deleted=True,
        ),
    ]
    db.add_all(milestones_a)

    # --- Milestones for project_b: 1 completed, 0 pending → 100% ---
    milestones_b = [
        ProjectMilestone(
            project_id=project_b.project_id,
            title="Requirements Gathering",
            target_date=date(2026, 4, 1),
            status=MilestoneStatus.COMPLETED,
            completed_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
        ),
    ]
    db.add_all(milestones_b)

    db.commit()

    data = {
        "client_a_account": client_a_account,
        "client_b_account": client_b_account,
        "employee_account": employee_account,
        "admin_account": admin_account,
        "pm_account": pm_account,
        "client_a": client_a,
        "client_b": client_b,
        "project_a": project_a,
        "project_b": project_b,
        "project_a2": project_a2,
    }
    db.close()
    return data


# ==============================================================================
# Helper: create a TestClient impersonating a given user
# ==============================================================================

def _client_as(app: FastAPI, user: UserAccount) -> TestClient:
    """Return a TestClient where get_current_user is overridden to *user*."""
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


# ==============================================================================
# 1. RBAC – Only CLIENT role is permitted
# ==============================================================================

class TestRBAC:
    """Non-CLIENT roles must receive 403 Forbidden on all client portal endpoints."""

    def test_unauthenticated_returns_401(self, app):
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 401

    def test_employee_forbidden_projects(self, app, seed_data):
        client = _client_as(app, seed_data["employee_account"])
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 403

    def test_admin_forbidden_projects(self, app, seed_data):
        client = _client_as(app, seed_data["admin_account"])
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 403

    def test_pm_forbidden_projects(self, app, seed_data):
        client = _client_as(app, seed_data["pm_account"])
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 403

    def test_employee_forbidden_milestones(self, app, seed_data):
        client = _client_as(app, seed_data["employee_account"])
        res = client.get(f"/api/v1/client/projects/{seed_data['project_a'].project_id}/milestones")
        assert res.status_code == 403

    def test_admin_forbidden_milestones(self, app, seed_data):
        client = _client_as(app, seed_data["admin_account"])
        res = client.get(f"/api/v1/client/projects/{seed_data['project_a'].project_id}/milestones")
        assert res.status_code == 403


# ==============================================================================
# 2. GET /api/v1/client/projects – Scoped project listing
# ==============================================================================

class TestClientProjects:
    """Client A sees only Client A's projects, with correct metrics."""

    def test_client_a_sees_own_projects(self, app, seed_data):
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 200
        data = res.json()
        # Client A has 2 projects (project_a and project_a2)
        assert len(data) == 2
        codes = {p["project_code"] for p in data}
        assert "PRJ-ACME-001" in codes
        assert "PRJ-ACME-002" in codes
        # Must NOT contain Globex project
        assert "PRJ-GLX-001" not in codes

    def test_client_b_sees_own_projects(self, app, seed_data):
        client = _client_as(app, seed_data["client_b_account"])
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["project_code"] == "PRJ-GLX-001"

    def test_completion_pct_50_percent(self, app, seed_data):
        """Project A has 2 completed, 2 pending (non-deleted) → 50.0%."""
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects")
        data = res.json()
        proj_a = next(p for p in data if p["project_code"] == "PRJ-ACME-001")
        assert proj_a["completion_pct"] == 50.0
        assert proj_a["milestones_summary"]["total"] == 4
        assert proj_a["milestones_summary"]["completed"] == 2
        assert proj_a["milestones_summary"]["pending"] == 2

    def test_completion_pct_zero_no_milestones(self, app, seed_data):
        """Project A2 has no milestones → 0.0%."""
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects")
        data = res.json()
        proj_a2 = next(p for p in data if p["project_code"] == "PRJ-ACME-002")
        assert proj_a2["completion_pct"] == 0.0
        assert proj_a2["milestones_summary"]["total"] == 0

    def test_completion_pct_100_percent(self, app, seed_data):
        """Project B has 1 completed, 0 pending → 100.0%."""
        client = _client_as(app, seed_data["client_b_account"])
        res = client.get("/api/v1/client/projects")
        data = res.json()
        proj_b = data[0]
        assert proj_b["completion_pct"] == 100.0
        assert proj_b["milestones_summary"]["total"] == 1
        assert proj_b["milestones_summary"]["completed"] == 1
        assert proj_b["milestones_summary"]["pending"] == 0

    def test_target_end_date_mapped(self, app, seed_data):
        """Project.end_date must appear as target_end_date in response."""
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects")
        data = res.json()
        proj_a = next(p for p in data if p["project_code"] == "PRJ-ACME-001")
        assert proj_a["target_end_date"] == "2026-06-30"
        # Project A2 has no end_date
        proj_a2 = next(p for p in data if p["project_code"] == "PRJ-ACME-002")
        assert proj_a2["target_end_date"] is None

    def test_response_redacts_internal_fields(self, app, seed_data):
        """Response must NOT contain pm_id, employee data, or internal notes."""
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects")
        raw_text = res.text
        assert "pm_id" not in raw_text
        assert "emp_id" not in raw_text
        assert "employee" not in raw_text.lower()
        assert "salary" not in raw_text.lower()
        expected_keys = {
            "project_id",
            "project_code",
            "name",
            "description",
            "status",
            "start_date",
            "target_end_date",
            "completion_pct",
            "milestones_summary",
        }
        for proj in res.json():
            assert set(proj.keys()) == expected_keys


# ==============================================================================
# 3. GET /api/v1/client/projects/{id}/milestones – Scoped milestones
# ==============================================================================

class TestClientMilestones:
    """Milestone listing is scoped and returns only active milestones."""

    def test_client_a_own_milestones(self, app, seed_data):
        client = _client_as(app, seed_data["client_a_account"])
        pid = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/milestones")
        assert res.status_code == 200
        data = res.json()
        # 4 active milestones (soft-deleted one excluded)
        assert len(data) == 4
        titles = [m["title"] for m in data]
        assert "Design Mockups" in titles
        assert "Frontend Build" in titles
        assert "Backend Integration" in titles
        assert "UAT & Launch" in titles
        # Soft-deleted must not appear
        assert "Deleted Phase" not in titles

    def test_milestones_ordered_by_target_date(self, app, seed_data):
        client = _client_as(app, seed_data["client_a_account"])
        pid = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/milestones")
        data = res.json()
        dates = [m["target_date"] for m in data]
        assert dates == sorted(dates)

    def test_milestone_completed_at_present(self, app, seed_data):
        client = _client_as(app, seed_data["client_a_account"])
        pid = seed_data["project_a"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/milestones")
        data = res.json()
        completed = [m for m in data if m["status"] == "completed"]
        for m in completed:
            assert m["completed_at"] is not None
        pending = [m for m in data if m["status"] == "pending"]
        for m in pending:
            assert m["completed_at"] is None

    def test_cross_client_project_returns_404(self, app, seed_data):
        """Client A trying to view Client B's project milestones → 404."""
        client = _client_as(app, seed_data["client_a_account"])
        pid_b = seed_data["project_b"].project_id
        res = client.get(f"/api/v1/client/projects/{pid_b}/milestones")
        assert res.status_code == 404

    def test_nonexistent_project_returns_404(self, app, seed_data):
        client = _client_as(app, seed_data["client_a_account"])
        res = client.get("/api/v1/client/projects/999999/milestones")
        assert res.status_code == 404

    def test_empty_milestones_project(self, app, seed_data):
        """Project A2 has no milestones — returns empty list, not 404."""
        client = _client_as(app, seed_data["client_a_account"])
        pid = seed_data["project_a2"].project_id
        res = client.get(f"/api/v1/client/projects/{pid}/milestones")
        assert res.status_code == 200
        assert res.json() == []


# ==============================================================================
# 4. Client with no Client profile → 403
# ==============================================================================

class TestNoClientProfile:
    """A CLIENT-type user with no linked Client record gets 403."""

    def test_client_user_without_profile_gets_403_projects(self, app, TestSessionLocal):
        db = TestSessionLocal()
        orphan = UserAccount(
            account_id=uuid.UUID("ffff0000-0000-0000-0000-000000000099"),
            email="orphan@nowhere.com",
            password_hash="hashed",
            user_type=UserType.CLIENT,
            is_active=True,
        )
        db.add(orphan)
        db.commit()
        db.close()

        client = _client_as(app, orphan)
        res = client.get("/api/v1/client/projects")
        assert res.status_code == 403
        assert "not registered" in res.json()["detail"].lower()

    def test_client_user_without_profile_gets_403_milestones(self, app, TestSessionLocal):
        db = TestSessionLocal()
        orphan = db.query(UserAccount).filter(
            UserAccount.email == "orphan@nowhere.com"
        ).first()
        db.close()

        client = _client_as(app, orphan)
        res = client.get("/api/v1/client/projects/1/milestones")
        assert res.status_code == 403
