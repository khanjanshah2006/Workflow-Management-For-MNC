"""
Unit and Integration tests for Project Milestones Feature (US-08).
Covers schema validation, model attributes, service business logic, RBAC authorization,
date validation, completion timestamping, audit logging, and task/deliverable FK compatibility.
"""

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.enums import (
    AuditAction,
    CommonStatus,
    DeliverableStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    UserType,
)
from app.models.user_account import UserAccount
from app.models.client import Client
from app.models.employee import Employee
from app.models.project_manager import ProjectManager
from app.models.project import Project, ProjectAssignment
from app.models.milestone import ProjectMilestone, Milestone
from app.models.task import Task
from app.models.deliverable import Deliverable
from app.models.audit_log import AuditLog
from app.features.projects.schemas import (
    MilestoneCreate,
    MilestoneUpdate,
    MilestoneResponse,
)
from app.features.projects.service import (
    ProjectService,
    ProjectNotFoundError,
    MilestoneNotFoundError,
    InvalidDateRangeError,
    UnauthorizedProjectAccessError,
)
from app.features.projects.router import router as project_router


# ==============================================================================
# Test Fixtures & In-Memory SQLite Setup
# ==============================================================================

@pytest.fixture
def db_session():
    """Isolated SQLite database session for unit tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            UserAccount.__table__,
            Client.__table__,
            Employee.__table__,
            ProjectManager.__table__,
            Project.__table__,
            ProjectAssignment.__table__,
            ProjectMilestone.__table__,
            Task.__table__,
            Deliverable.__table__,
            AuditLog.__table__,
        ],
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app_client(db_session):
    """FastAPI test client with database dependency override."""
    app = FastAPI()
    app.include_router(project_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, app, db_session


@pytest.fixture
def seed_data(db_session):
    """Seed test accounts, project manager, client, projects, and employees."""
    # 1. Accounts
    pm1_acc_id = uuid4()
    pm1_account = UserAccount(
        account_id=pm1_acc_id,
        email="pm1@company.com",
        password_hash="fakehash",
        user_type=UserType.PM,
        is_active=True,
    )
    pm2_acc_id = uuid4()
    pm2_account = UserAccount(
        account_id=pm2_acc_id,
        email="pm2@company.com",
        password_hash="fakehash",
        user_type=UserType.PM,
        is_active=True,
    )
    admin_acc_id = uuid4()
    admin_account = UserAccount(
        account_id=admin_acc_id,
        email="admin@company.com",
        password_hash="fakehash",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    emp_acc_id = uuid4()
    emp_account = UserAccount(
        account_id=emp_acc_id,
        email="emp@company.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    unassigned_emp_acc_id = uuid4()
    unassigned_emp_account = UserAccount(
        account_id=unassigned_emp_acc_id,
        email="unassigned@company.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([pm1_account, pm2_account, admin_account, emp_account, unassigned_emp_account])
    db_session.flush()

    # 2. Project Managers
    pm1 = ProjectManager(
        pm_id=1,
        account_id=pm1_acc_id,
        emp_code="PM-001",
        full_name="Sarah PM",
        email="pm1@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    pm2 = ProjectManager(
        pm_id=2,
        account_id=pm2_acc_id,
        emp_code="PM-002",
        full_name="John PM",
        email="pm2@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([pm1, pm2])

    # 3. Employees
    emp = Employee(
        emp_id=1,
        account_id=emp_acc_id,
        emp_code="EMP-001",
        full_name="Bob Dev",
        designation="Software Engineer",
        email="emp@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    unassigned_emp = Employee(
        emp_id=2,
        account_id=unassigned_emp_acc_id,
        emp_code="EMP-002",
        full_name="Charlie Other",
        designation="QA Engineer",
        email="unassigned@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([emp, unassigned_emp])
    db_session.flush()

    # 4. Client
    client = Client(
        client_id=1,
        company_name="Acme Corp",
        contact_person="Alice Smith",
        email="alice@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db_session.add(client)
    db_session.flush()

    # 5. Projects (proj1 managed by PM1, proj2 open-ended managed by PM1, proj3 managed by PM2)
    proj1 = Project(
        project_id=1,
        client_id=1,
        pm_id=1,
        project_code="PRJ-ALPHA",
        name="Alpha Project",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    proj2 = Project(
        project_id=2,
        client_id=1,
        pm_id=1,
        project_code="PRJ-OPEN",
        name="Open Ended Project",
        start_date=date(2026, 1, 1),
        end_date=None,
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    proj3 = Project(
        project_id=3,
        client_id=1,
        pm_id=2,
        project_code="PRJ-BETA",
        name="Beta Project",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 8, 31),
        priority=PriorityLevel.LOW,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add_all([proj1, proj2, proj3])
    db_session.flush()

    # 6. Project Assignment (emp assigned to proj1)
    assignment = ProjectAssignment(
        assignment_id=1,
        project_id=1,
        emp_id=1,
        role_in_project="Backend Developer",
        assigned_on=date(2026, 1, 1),
    )
    db_session.add(assignment)
    db_session.commit()

    return {
        "pm1_account": pm1_account,
        "pm2_account": pm2_account,
        "admin_account": admin_account,
        "emp_account": emp_account,
        "unassigned_emp_account": unassigned_emp_account,
        "pm1": pm1,
        "pm2": pm2,
        "emp": emp,
        "unassigned_emp": unassigned_emp,
        "client": client,
        "proj1": proj1,
        "proj2": proj2,
        "proj3": proj3,
    }


# ==============================================================================
# 1. Model & Schema Unit Tests
# ==============================================================================

def test_milestone_schema_valid_creation():
    """MilestoneCreate accepts valid title, target_date, description, and status."""
    payload = {
        "title": "Database Schema Finalized",
        "description": "All 27 entities migrated",
        "target_date": "2026-03-15",
        "status": "pending",
    }
    schema = MilestoneCreate.model_validate(payload)
    assert schema.title == "Database Schema Finalized"
    assert schema.target_date == date(2026, 3, 15)
    assert schema.status == MilestoneStatus.PENDING


def test_milestone_schema_case_insensitive_status():
    """MilestoneCreate normalizes status case (e.g., PENDING, Pending -> pending)."""
    for status_str in ["PENDING", "pending", "Pending"]:
        schema = MilestoneCreate.model_validate({
            "title": "Phase 1",
            "target_date": "2026-04-01",
            "status": status_str,
        })
        assert schema.status == MilestoneStatus.PENDING

    for status_str in ["COMPLETED", "completed", "Completed"]:
        schema = MilestoneCreate.model_validate({
            "title": "Phase 1",
            "target_date": "2026-04-01",
            "status": status_str,
        })
        assert schema.status == MilestoneStatus.COMPLETED


def test_milestone_schema_reject_invalid_status():
    """MilestoneCreate rejects invalid status strings not in MilestoneStatus."""
    with pytest.raises(ValidationError):
        MilestoneCreate.model_validate({
            "title": "Sprint Review",
            "target_date": "2026-03-01",
            "status": "invalid_status",
        })


def test_milestone_schema_blank_title_rejected():
    """MilestoneCreate rejects empty or whitespace-only title."""
    with pytest.raises(ValidationError):
        MilestoneCreate.model_validate({
            "title": "   ",
            "target_date": "2026-03-15",
        })


def test_milestone_schema_default_status():
    """MilestoneCreate defaults status to PENDING if omitted."""
    schema = MilestoneCreate.model_validate({
        "title": "Core Setup",
        "target_date": "2026-02-15",
    })
    assert schema.status == MilestoneStatus.PENDING


def test_milestone_model_backward_compat_properties():
    """ProjectMilestone model properties milestone_id and due_date provide aliases."""
    m = ProjectMilestone(
        id=42,
        project_id=1,
        title="Test",
        target_date=date(2026, 3, 1),
        status=MilestoneStatus.PENDING,
    )
    assert m.milestone_id == 42
    assert m.due_date == date(2026, 3, 1)


# ==============================================================================
# 2. Business Logic Unit Tests
# ==============================================================================

def test_service_create_milestone_date_validation_before_start(db_session, seed_data):
    """Rejects milestone when target_date is before project start_date."""
    payload = MilestoneCreate(
        title="Early Milestone",
        target_date=date(2025, 12, 31),  # Project starts 2026-01-01
    )
    with pytest.raises(InvalidDateRangeError) as exc_info:
        ProjectService.create_milestone(
            db=db_session,
            project_id=1,
            payload=payload,
            current_user=seed_data["pm1_account"],
        )
    assert "cannot be before project start_date" in str(exc_info.value)


def test_service_create_milestone_date_validation_after_end(db_session, seed_data):
    """Rejects milestone when target_date is after project end_date."""
    payload = MilestoneCreate(
        title="Late Milestone",
        target_date=date(2026, 7, 1),  # Project ends 2026-06-30
    )
    with pytest.raises(InvalidDateRangeError) as exc_info:
        ProjectService.create_milestone(
            db=db_session,
            project_id=1,
            payload=payload,
            current_user=seed_data["pm1_account"],
        )
    assert "cannot be after project end_date" in str(exc_info.value)


def test_service_create_milestone_open_ended_project(db_session, seed_data):
    """Allows milestone target_date in the far future if project has no end_date."""
    payload = MilestoneCreate(
        title="Future Goal",
        target_date=date(2028, 12, 31),
    )
    m = ProjectService.create_milestone(
        db=db_session,
        project_id=2,  # proj2 has end_date=None
        payload=payload,
        current_user=seed_data["pm1_account"],
    )
    assert m.id is not None
    assert m.target_date == date(2028, 12, 31)


def test_service_create_milestone_unauthorized_pm(db_session, seed_data):
    """Non-assigned PM cannot create a milestone in someone else's project."""
    payload = MilestoneCreate(
        title="Unauthorized Milestone",
        target_date=date(2026, 3, 1),
    )
    with pytest.raises(UnauthorizedProjectAccessError):
        ProjectService.create_milestone(
            db=db_session,
            project_id=1,  # Managed by PM1
            payload=payload,
            current_user=seed_data["pm2_account"],  # PM2 tries to create
        )


def test_service_create_milestone_admin_authorized(db_session, seed_data):
    """System Administrator can create a milestone in any project."""
    payload = MilestoneCreate(
        title="Admin Created Milestone",
        target_date=date(2026, 3, 1),
    )
    m = ProjectService.create_milestone(
        db=db_session,
        project_id=1,
        payload=payload,
        current_user=seed_data["admin_account"],
    )
    assert m.id is not None
    assert m.title == "Admin Created Milestone"


def test_service_update_milestone_mark_completed_timestamp(db_session, seed_data):
    """Marking milestone completed records completed_at timestamp and creates audit log."""
    payload = MilestoneCreate(
        title="Frontend Prototype",
        target_date=date(2026, 4, 15),
    )
    created = ProjectService.create_milestone(
        db=db_session,
        project_id=1,
        payload=payload,
        current_user=seed_data["pm1_account"],
    )
    assert created.status == MilestoneStatus.PENDING
    assert created.completed_at is None

    # Update to completed
    update_payload = MilestoneUpdate(status=MilestoneStatus.COMPLETED)
    updated = ProjectService.update_milestone(
        db=db_session,
        project_id=1,
        milestone_id=created.id,
        payload=update_payload,
        current_user=seed_data["pm1_account"],
    )
    assert updated.status == MilestoneStatus.COMPLETED
    assert updated.completed_at is not None

    # Check audit log
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_name == "PROJECT_MILESTONE",
        AuditLog.action == AuditAction.UPDATE,
        AuditLog.entity_ref_id == str(created.id),
    ).first()
    assert audit is not None
    assert audit.account_id == seed_data["pm1_account"].account_id
    old_data = json.loads(audit.old_value)
    new_data = json.loads(audit.new_value)
    assert old_data["status"] == "pending"
    assert new_data["status"] == "completed"


def test_update_already_completed_milestone_preserves_completed_at(db_session, seed_data):
    """Updating details on an already-completed milestone does not overwrite completed_at."""
    payload = MilestoneCreate(
        title="Initial Version",
        target_date=date(2026, 3, 1),
        status=MilestoneStatus.COMPLETED,
    )
    created = ProjectService.create_milestone(
        db=db_session,
        project_id=1,
        payload=payload,
        current_user=seed_data["pm1_account"],
    )
    initial_completed_at = created.completed_at
    assert initial_completed_at is not None

    # Update title and keep status completed
    updated = ProjectService.update_milestone(
        db=db_session,
        project_id=1,
        milestone_id=created.id,
        payload=MilestoneUpdate(title="Revised Title", status=MilestoneStatus.COMPLETED),
        current_user=seed_data["pm1_account"],
    )
    assert updated.title == "Revised Title"
    assert updated.completed_at == initial_completed_at


def test_reopening_completed_milestone_clears_completed_at(db_session, seed_data):
    """Reopening a completed milestone as pending clears completed_at."""
    payload = MilestoneCreate(
        title="Feature Testing",
        target_date=date(2026, 3, 1),
        status=MilestoneStatus.COMPLETED,
    )
    created = ProjectService.create_milestone(
        db=db_session,
        project_id=1,
        payload=payload,
        current_user=seed_data["pm1_account"],
    )
    assert created.completed_at is not None

    reopened = ProjectService.update_milestone(
        db=db_session,
        project_id=1,
        milestone_id=created.id,
        payload=MilestoneUpdate(status=MilestoneStatus.PENDING),
        current_user=seed_data["pm1_account"],
    )
    assert reopened.status == MilestoneStatus.PENDING
    assert reopened.completed_at is None


def test_service_soft_delete_milestone(db_session, seed_data):
    """Soft deleting milestone flags is_deleted=True and excludes from list."""
    payload = MilestoneCreate(
        title="To Be Deleted",
        target_date=date(2026, 5, 1),
    )
    created = ProjectService.create_milestone(
        db=db_session,
        project_id=1,
        payload=payload,
        current_user=seed_data["pm1_account"],
    )

    # Delete
    del_res = ProjectService.delete_milestone(
        db=db_session,
        project_id=1,
        milestone_id=created.id,
        current_user=seed_data["pm1_account"],
    )
    assert del_res["id"] == created.id

    # Check listing excludes it
    active_milestones = ProjectService.list_milestones(db=db_session, project_id=1)
    assert all(m.id != created.id for m in active_milestones)

    # Check audit entry for DELETE
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_name == "PROJECT_MILESTONE",
        AuditLog.action == AuditAction.DELETE,
        AuditLog.entity_ref_id == str(created.id),
    ).first()
    assert audit is not None


def test_task_and_deliverable_foreign_key_compatibility(db_session, seed_data):
    """Verify task and deliverable can link to project_milestone and set null on delete."""
    milestone = ProjectMilestone(
        project_id=1,
        title="Delivery Milestone",
        target_date=date(2026, 4, 1),
        status=MilestoneStatus.PENDING,
    )
    db_session.add(milestone)
    db_session.commit()
    db_session.refresh(milestone)

    # Create task linked to milestone
    task = Task(
        project_id=1,
        milestone_id=milestone.id,
        title="Implement Task",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.TODO,
    )
    deliverable = Deliverable(
        project_id=1,
        milestone_id=milestone.id,
        title="Release Archive",
        file_url="https://storage.example.com/v1.zip",
        version=1,
        status=DeliverableStatus.SUBMITTED,
    )
    db_session.add_all([task, deliverable])
    db_session.commit()

    assert task.milestone_id == milestone.id
    assert deliverable.milestone_id == milestone.id


# ==============================================================================
# 3. API Integration Tests (All CRUD Endpoints & Edge Cases)
# ==============================================================================

def test_api_create_milestone_201_success(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: PM adds milestone successfully."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.post(
        "/api/v1/projects/1/milestones",
        json={
            "title": "Sprint 1 Deliverable",
            "description": "API endpoints completed",
            "target_date": "2026-02-28",
            "status": "pending",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["project_id"] == 1
    assert data["title"] == "Sprint 1 Deliverable"
    assert data["target_date"] == "2026-02-28"
    assert data["status"] == "pending"
    assert data["completed_at"] is None


def test_api_create_milestone_422_invalid_status(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: 422 Unprocessable Entity on invalid status."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Test", "target_date": "2026-03-01", "status": "unknown_status"},
    )
    assert response.status_code == 422


def test_api_create_milestone_400_date_out_of_bounds(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: 400 when target_date outside project dates."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    # Target date before project start (2026-01-01)
    res_early = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Too Early", "target_date": "2025-11-15"},
    )
    assert res_early.status_code == 400
    assert "cannot be before project start_date" in res_early.json()["detail"]

    # Target date after project end (2026-06-30)
    res_late = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Too Late", "target_date": "2026-07-15"},
    )
    assert res_late.status_code == 400
    assert "cannot be after project end_date" in res_late.json()["detail"]


def test_api_create_milestone_403_unauthorized_pm(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: 403 when non-assigned PM attempts creation."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm2_account"]

    response = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Unauthorized Milestone", "target_date": "2026-03-01"},
    )
    assert response.status_code == 403
    assert "Only the assigned Project Manager" in response.json()["detail"]


def test_api_create_milestone_403_employee_forbidden(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: 403 when regular Employee attempts creation."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["emp_account"]

    response = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Employee Milestone", "target_date": "2026-03-01"},
    )
    assert response.status_code == 403


def test_api_create_milestone_404_project_not_found(app_client, seed_data):
    """POST /api/v1/projects/{id}/milestones: 404 when project does not exist."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.post(
        "/api/v1/projects/99999/milestones",
        json={"title": "Non-existent Project", "target_date": "2026-03-01"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_api_list_milestones_200_ordered_by_target_date(app_client, seed_data):
    """GET /api/v1/projects/{id}/milestones: Returns milestones ordered by target_date ASC."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    # Insert milestones out of chronological order
    client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Milestone C", "target_date": "2026-05-01"},
    )
    client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Milestone A", "target_date": "2026-02-01"},
    )
    client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Milestone B", "target_date": "2026-03-15"},
    )

    # Assigned employee can view milestones
    app.dependency_overrides[get_current_user] = lambda: seed_data["emp_account"]
    response = client.get("/api/v1/projects/1/milestones")
    assert response.status_code == 200
    milestones = response.json()
    assert len(milestones) == 3
    assert milestones[0]["title"] == "Milestone A"
    assert milestones[1]["title"] == "Milestone B"
    assert milestones[2]["title"] == "Milestone C"


def test_api_list_milestones_403_unrelated_user(app_client, seed_data):
    """GET /api/v1/projects/{id}/milestones: 403 when user has no assignment or management role."""
    client, app, _ = app_client
    # Unassigned employee
    app.dependency_overrides[get_current_user] = lambda: seed_data["unassigned_emp_account"]
    res_emp = client.get("/api/v1/projects/1/milestones")
    assert res_emp.status_code == 403

    # PM2 who manages project 3, not project 1
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm2_account"]
    res_pm = client.get("/api/v1/projects/1/milestones")
    assert res_pm.status_code == 403


def test_api_update_milestone_200_and_mark_completed(app_client, seed_data, db_session):
    """PUT /api/v1/projects/{id}/milestones/{mid}: Updates details and records completion timestamp."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    # Create milestone
    create_res = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Beta Testing", "target_date": "2026-04-01"},
    )
    milestone_id = create_res.json()["id"]

    # Update title and mark completed
    update_res = client.put(
        f"/api/v1/projects/1/milestones/{milestone_id}",
        json={
            "title": "Beta Testing Completed",
            "status": "completed",
        },
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["title"] == "Beta Testing Completed"
    assert data["status"] == "completed"
    assert data["completed_at"] is not None

    # Verify audit log in DB
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_name == "PROJECT_MILESTONE",
        AuditLog.action == AuditAction.UPDATE,
        AuditLog.entity_ref_id == str(milestone_id),
    ).first()
    assert audit is not None
    assert json.loads(audit.new_value)["status"] == "completed"


def test_api_update_milestone_400_invalid_date(app_client, seed_data):
    """PUT /api/v1/projects/{id}/milestones/{mid}: 400 when updating to date outside project range."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    create_res = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Valid Milestone", "target_date": "2026-03-01"},
    )
    mid = create_res.json()["id"]

    # Try setting target_date after project end_date
    res = client.put(
        f"/api/v1/projects/1/milestones/{mid}",
        json={"target_date": "2026-08-01"},
    )
    assert res.status_code == 400
    assert "cannot be after project end_date" in res.json()["detail"]


def test_api_update_milestone_404_not_found(app_client, seed_data):
    """PUT /api/v1/projects/{id}/milestones/{mid}: 404 when milestone does not exist."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    res = client.put(
        "/api/v1/projects/1/milestones/99999",
        json={"title": "Missing Milestone"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_api_milestone_belongs_to_another_project_404(app_client, seed_data):
    """Reject accessing/updating a milestone belonging to another project (returns 404)."""
    client, app, _ = app_client
    # PM1 creates milestone on proj1
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]
    m1 = client.post("/api/v1/projects/1/milestones", json={"title": "M1", "target_date": "2026-03-01"}).json()
    mid = m1["id"]

    # PM1 also manages proj2. Try to update milestone 1 via proj2 endpoint
    res = client.put(
        f"/api/v1/projects/2/milestones/{mid}",
        json={"title": "Cross Project Update"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]

    # Try to delete milestone 1 via proj2 endpoint
    del_res = client.delete(f"/api/v1/projects/2/milestones/{mid}")
    assert del_res.status_code == 404


def test_api_delete_milestone_200_and_exclude_from_list(app_client, seed_data):
    """DELETE /api/v1/projects/{id}/milestones/{mid}: Soft deletes milestone and excludes from list."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    # Create milestone
    create_res = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Ephemeral Milestone", "target_date": "2026-03-10"},
    )
    mid = create_res.json()["id"]

    # Delete
    del_res = client.delete(f"/api/v1/projects/1/milestones/{mid}")
    assert del_res.status_code == 200
    assert del_res.json()["id"] == mid

    # Subsequent GET excludes it
    list_res = client.get("/api/v1/projects/1/milestones")
    assert all(m["id"] != mid for m in list_res.json())

    # Subsequent DELETE returns 404
    del_again = client.delete(f"/api/v1/projects/1/milestones/{mid}")
    assert del_again.status_code == 404


def test_api_delete_milestone_403_unauthorized_pm(app_client, seed_data):
    """DELETE /api/v1/projects/{id}/milestones/{mid}: 403 when non-assigned PM tries to delete."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    create_res = client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "Protected Milestone", "target_date": "2026-03-10"},
    )
    mid = create_res.json()["id"]

    # PM2 attempts delete
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm2_account"]
    del_res = client.delete(f"/api/v1/projects/1/milestones/{mid}")
    assert del_res.status_code == 403
