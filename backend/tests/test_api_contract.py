"""
API contract tests and notification verification (US-19).

Covers:
  - test_project_assignment_notifies_employee()
  - test_reallocation_notifies_new_assignee()
  - test_deliverable_shared_notifies_client()
  - test_task_summary_includes_blocker_and_rejections()
  - test_list_contract_keys()
  - test_client_portal_deliverables_get_allows_admin()
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.core.notification_types import (
    DELIVERABLE_SHARED,
    PROJECT_ASSIGNED,
    TASK_ASSIGNED,
    TASK_REASSIGNED,
)
from app.db.base import Base
from app.db.session import get_db
from app.features.admin.schemas import UserAccountPaginationResponse, UserAccountResponse
from app.features.client_portal.router import (
    project_deliverables_router,
    router as client_portal_router,
)
from app.features.notifications.router import router as notifications_router
from app.features.notifications.schemas import NotificationOut, PaginatedNotifications
from app.features.projects.router import router as projects_router
from app.features.projects.schemas import ProjectResponse
from app.features.support.schemas import TicketOut
from app.features.tasks.router import router as tasks_router
from app.features.tasks.schemas import PaginatedTasksResponse, TaskSummaryResponse
from app.models.client import Client
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    LeaveStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    UserType,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.notification import Notification
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture(scope="module")
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


@pytest.fixture(scope="module")
def app(SessionLocal):
    _app = FastAPI()
    _app.include_router(projects_router)
    _app.include_router(client_portal_router)
    _app.include_router(project_deliverables_router)
    _app.include_router(tasks_router)
    _app.include_router(notifications_router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    _app.dependency_overrides[get_db] = override_get_db
    yield _app
    _app.dependency_overrides.clear()


def as_user(app: FastAPI, user: UserAccount) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


# ------------------------------------------------------------------------------
# 1. Project Assignment Notifies Employee
# ------------------------------------------------------------------------------

def test_project_assignment_notifies_employee(app, SessionLocal):
    db = SessionLocal()

    # Create PM
    pm_acc = UserAccount(
        account_id=uuid.uuid4(), email="pm_assign@test.com", password_hash="pw",
        user_type=UserType.PM, is_active=True,
    )
    emp_acc = UserAccount(
        account_id=uuid.uuid4(), email="emp_assign@test.com", password_hash="pw",
        user_type=UserType.EMPLOYEE, is_active=True,
    )
    db.add_all([pm_acc, emp_acc])
    db.flush()

    pm = ProjectManager(
        account_id=pm_acc.account_id, emp_code="PM-ASSGN", full_name="PM Assign",
        email="pm_assign@test.com", date_of_joining=date(2024, 1, 1),
    )
    emp = Employee(
        account_id=emp_acc.account_id, emp_code="EMP-ASSGN", full_name="Emp Assign",
        email="emp_assign@test.com", designation="Backend Dev", date_of_joining=date(2024, 1, 1),
    )
    client = Client(
        company_name="Client Assign", contact_person="Bob", email="client_assign@test.com",
    )
    db.add_all([pm, emp, client])
    db.flush()

    project = Project(
        client_id=client.client_id, pm_id=pm.pm_id, project_code="PRJ-ASSGN",
        name="Assignment Notification Project", start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    db.commit()

    # Call assign endpoint as PM
    client_http = as_user(app, pm_acc)
    res = client_http.post(
        f"/api/v1/projects/{project.project_id}/assign",
        json={"emp_id": emp.emp_id, "role_in_project": "Lead Developer"},
    )
    assert res.status_code in (200, 201), res.text

    # Verify notification created for emp_acc.account_id
    notif = db.query(Notification).filter_by(
        account_id=emp_acc.account_id, type=PROJECT_ASSIGNED
    ).first()
    assert notif is not None, "PROJECT_ASSIGNED notification not found for employee"
    assert "Assignment Notification Project" in notif.message
    assert "Lead Developer" in notif.message
    db.close()


# ------------------------------------------------------------------------------
# 2. Leave Reallocation Notifies Assignee and Applicant
# ------------------------------------------------------------------------------

def test_reallocation_notifies_new_assignee(SessionLocal):
    from app.features.leave.reallocation_service import LeaveReallocationService
    from app.features.leave.schemas import TaskReallocationActionIn, TaskReallocationActionType, TaskReallocationBatchIn

    db = SessionLocal()

    admin_acc = UserAccount(
        account_id=uuid.uuid4(), email="admin_realloc@test.com", password_hash="pw",
        user_type=UserType.ADMIN, is_active=True,
    )
    app_acc = UserAccount(
        account_id=uuid.uuid4(), email="app_realloc@test.com", password_hash="pw",
        user_type=UserType.EMPLOYEE, is_active=True,
    )
    target_acc = UserAccount(
        account_id=uuid.uuid4(), email="target_realloc@test.com", password_hash="pw",
        user_type=UserType.EMPLOYEE, is_active=True,
    )
    db.add_all([admin_acc, app_acc, target_acc])
    db.flush()

    app_emp = Employee(
        account_id=app_acc.account_id, emp_code="EMP-APPL", full_name="Applicant",
        email="app_realloc@test.com", designation="Dev", date_of_joining=date(2024, 1, 1),
    )
    target_emp = Employee(
        account_id=target_acc.account_id, emp_code="EMP-TRGT", full_name="Target",
        email="target_realloc@test.com", designation="Dev", date_of_joining=date(2024, 1, 1),
    )
    db.add_all([app_emp, target_emp])
    db.flush()

    client = Client(company_name="Realloc Corp", contact_person="Eve", email="realloc@corp.com")
    db.add(client)
    db.flush()

    pm_acc = UserAccount(
        account_id=uuid.uuid4(), email="pm_realloc@test.com", password_hash="pw",
        user_type=UserType.PM, is_active=True,
    )
    db.add(pm_acc)
    db.flush()
    pm = ProjectManager(
        account_id=pm_acc.account_id, emp_code="PM-RLC", full_name="PM Realloc",
        email="pm_realloc@test.com", date_of_joining=date(2024, 1, 1),
    )
    db.add(pm)
    db.flush()

    project = Project(
        client_id=client.client_id, pm_id=pm.pm_id, project_code="PRJ-RLC",
        name="Realloc Project", start_date=date(2026, 1, 1), status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    db.flush()

    # Team
    team = Team(project_id=project.project_id, name="Core Devs", status=CommonStatus.ACTIVE)
    db.add(team)
    db.flush()
    db.add_all([
        TeamMember(team_id=team.team_id, emp_id=app_emp.emp_id),
        TeamMember(team_id=team.team_id, emp_id=target_emp.emp_id),
    ])

    # Leave Type and Leave Request
    lt = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True)
    db.add(lt)
    db.flush()

    lr = LeaveRequest(
        emp_id=app_emp.emp_id, leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 1), end_date=date(2026, 12, 5),
        total_days=5, reason="Vacation trip with family", status=LeaveStatus.APPROVED,
    )
    db.add(lr)
    db.flush()

    # Task assigned to applicant due during leave
    task = Task(
        project_id=project.project_id, team_id=team.team_id,
        assigned_to=app_emp.emp_id, title="Implement Auth Hook",
        priority=PriorityLevel.HIGH, status=TaskStatus.IN_PROGRESS,
        progress_pct=20, due_date=date(2026, 12, 3),
    )
    db.add(task)
    db.commit()

    # Reallocate task to target_emp
    batch = TaskReallocationBatchIn(
        actions=[
            TaskReallocationActionIn(
                task_id=task.task_id,
                action_type=TaskReallocationActionType.REASSIGN,
                new_assignee_id=target_emp.emp_id,
                reason="Reassigned due to approved annual leave",
            )
        ]
    )
    res = LeaveReallocationService.reallocate_tasks(
        db=db,
        leave_id=lr.leave_id,
        batch=batch,
        current_user=admin_acc,
        today=date(2026, 11, 20),
    )
    assert res.reallocated_count == 1

    # Verify target employee received notification
    notes_new = db.query(Notification).filter_by(account_id=target_acc.account_id).all()
    assert any(n.type in (TASK_ASSIGNED, TASK_REASSIGNED) for n in notes_new), (
        "New assignee did not receive task assignment notification"
    )

    # Verify original leave applicant received summary notification
    notes_applicant = db.query(Notification).filter_by(account_id=app_acc.account_id).all()
    assert any(n.type == TASK_REASSIGNED for n in notes_applicant), (
        "Leave applicant did not receive summary TASK_REASSIGNED notification"
    )
    db.close()


# ------------------------------------------------------------------------------
# 3. Deliverable Sharing Notifies Client
# ------------------------------------------------------------------------------

def test_deliverable_shared_notifies_client(app, SessionLocal):
    db = SessionLocal()

    client_acc = UserAccount(
        account_id=uuid.uuid4(), email="client_deliv@test.com", password_hash="pw",
        user_type=UserType.CLIENT, is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid.uuid4(), email="pm_deliv@test.com", password_hash="pw",
        user_type=UserType.PM, is_active=True,
    )
    db.add_all([client_acc, pm_acc])
    db.flush()

    client = Client(
        account_id=client_acc.account_id, company_name="Acme Deliverables",
        contact_person="Alice", email="client_deliv@test.com", status=CommonStatus.ACTIVE,
    )
    pm = ProjectManager(
        account_id=pm_acc.account_id, emp_code="PM-DLV", full_name="PM Deliv",
        email="pm_deliv@test.com", date_of_joining=date(2024, 1, 1),
    )
    db.add_all([client, pm])
    db.flush()

    project = Project(
        client_id=client.client_id, pm_id=pm.pm_id, project_code="PRJ-DLV",
        name="Deliverable Notify Project", start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    db.commit()

    # PM publishes deliverable
    client_http = as_user(app, pm_acc)
    res = client_http.post(
        f"/api/v1/projects/{project.project_id}/deliverables",
        json={
            "title": "API Specification v1.0",
            "description": "Final OpenAPI 3.0 specs",
            "file_url": "https://s3.amazonaws.com/bucket/spec.pdf",
        },
    )
    assert res.status_code == 201, res.text

    # Verify DELIVERABLE_SHARED notification sent to client_acc.account_id
    notif = db.query(Notification).filter_by(
        account_id=client_acc.account_id, type=DELIVERABLE_SHARED
    ).first()
    assert notif is not None, "DELIVERABLE_SHARED notification not found for client account"
    assert "API Specification v1.0" in notif.message
    assert "PRJ-DLV" in notif.message
    db.close()


# ------------------------------------------------------------------------------
# 4. TaskSummaryResponse Includes Blocker Reason and Rejection Count
# ------------------------------------------------------------------------------

def test_task_summary_includes_blocker_and_rejections(SessionLocal):
    db = SessionLocal()

    task = Task(
        project_id=1, team_id=1, title="Blocked Integration Task",
        priority=PriorityLevel.CRITICAL, status=TaskStatus.BLOCKED,
        progress_pct=45, blocker_reason="Waiting for vendor API OAuth keys",
        rejection_count=3,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    summary = TaskSummaryResponse.model_validate(task)
    dumped = summary.model_dump()

    assert "blocker_reason" in dumped
    assert "rejection_count" in dumped
    assert summary.blocker_reason == "Waiting for vendor API OAuth keys"
    assert summary.rejection_count == 3
    db.close()


# ------------------------------------------------------------------------------
# 5. List Contract Keys Snapshots
# ------------------------------------------------------------------------------

def test_list_contract_keys():
    # 1. Notifications
    notif_keys = set(NotificationOut.model_fields.keys())
    assert {"id", "account_id", "type", "title", "message", "is_read", "created_at"}.issubset(notif_keys)

    paginated_notif_keys = set(PaginatedNotifications.model_fields.keys())
    assert {"items", "total", "page", "page_size"}.issubset(paginated_notif_keys)

    # 2. Tasks
    task_keys = set(TaskSummaryResponse.model_fields.keys())
    assert {
        "task_id", "project_id", "team_id", "title", "priority",
        "status", "progress_pct", "blocker_reason", "rejection_count",
    }.issubset(task_keys)

    paginated_tasks_keys = set(PaginatedTasksResponse.model_fields.keys())
    assert {"items", "total", "page", "limit"}.issubset(paginated_tasks_keys)

    # 3. Projects
    project_keys = set(ProjectResponse.model_fields.keys())
    assert {"project_id", "project_code", "name", "status", "priority", "client_id", "pm_id"}.issubset(project_keys)

    # 4. Admin Users
    user_keys = set(UserAccountResponse.model_fields.keys())
    assert {"account_id", "email", "user_type", "is_active", "created_at"}.issubset(user_keys)

    user_page_keys = set(UserAccountPaginationResponse.model_fields.keys())
    assert {"items", "total", "page", "limit", "total_pages"}.issubset(user_page_keys)

    # 5. Support Queue
    ticket_keys = set(TicketOut.model_fields.keys())
    assert {"id", "ticket_id", "ticket_number", "title", "description"}.issubset(ticket_keys)


# ------------------------------------------------------------------------------
# 6. Client Portal Deliverables GET Authorization Allows Admin
# ------------------------------------------------------------------------------

def test_client_portal_deliverables_get_allows_admin(app, SessionLocal):
    db = SessionLocal()

    admin_acc = UserAccount(
        account_id=uuid.uuid4(), email="admin_deliverables@test.com", password_hash="pw",
        user_type=UserType.ADMIN, is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid.uuid4(), email="pm_deliverables@test.com", password_hash="pw",
        user_type=UserType.PM, is_active=True,
    )
    db.add_all([admin_acc, pm_acc])
    db.flush()

    client = Client(
        company_name="Deliverables Corp", contact_person="Dave", email="client_deliv_get@test.com",
    )
    pm = ProjectManager(
        account_id=pm_acc.account_id, emp_code="PM-DGET", full_name="PM DGet",
        email="pm_deliverables@test.com", date_of_joining=date(2024, 1, 1),
    )
    db.add_all([client, pm])
    db.flush()

    project = Project(
        client_id=client.client_id, pm_id=pm.pm_id, project_code="PRJ-DGET",
        name="Deliverables Get Project", start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    db.flush()

    deliverable = Deliverable(
        project_id=project.project_id, title="Test Deliverable", file_url="https://test.com/doc.pdf",
    )
    db.add(deliverable)
    db.commit()

    # Query as ADMIN
    client_http = as_user(app, admin_acc)
    res = client_http.get(f"/api/v1/client/projects/{project.project_id}/deliverables")
    assert res.status_code in (200, 201), res.text
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["title"] == "Test Deliverable"
    db.close()
