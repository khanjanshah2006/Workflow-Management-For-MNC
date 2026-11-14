"""
Unit and Integration tests for US-12 (Review Task).

Acceptance Criteria:
- Team Lead of task's team can approve task awaiting review (status=IN_REVIEW).
- Approving sets status = 'DONE', progress_pct = 100, and non-null completed_at.
- Approving all tasks in a milestone recalculates milestone status to 'completed'.
- Dispatches 'TASK_APPROVED' notification to the assigned employee.
- Rejecting with mandatory feedback (min 10 chars) sets status = 'REJECTED'.
- Rejecting sets rejection_feedback and increments rejection_count by exactly 1.
- Dispatches 'TASK_REJECTED' notification with feedback text to assigned employee.
- Rejecting without feedback returns 422 Unprocessable Entity.
- Attempting to review a task in TODO, IN_PROGRESS, or DONE returns 400 Bad Request ('Task is not awaiting review.').
- Unauthorized regular employees cannot review tasks (403 Forbidden).
- Team Lead of an unrelated team cannot review (403 Forbidden).
- Project Manager of the project can review tasks (200 OK).
- Project Manager of a different project cannot review (403 Forbidden).
- System Administrator can review tasks (200 OK).
- Audit log is written for both APPROVE and REJECT.
"""

from datetime import date, datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import CommonStatus, MilestoneStatus, PriorityLevel, ProjectStatus, TaskStatus, TeamStatus, UserType
from app.models.milestone import ProjectMilestone
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def test_setup(db_session):
    """Seed prerequisite test entities: department, accounts, employees, project, team, milestones, and tasks."""
    # 1. Department
    dept = Department(dept_id=1, name="Core Engineering", description="Engineering division")
    db_session.add(dept)

    # 2. User Accounts
    emp1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp1@company.com",
        password_hash="testpass",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    lead_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="lead@company.com",
        password_hash="testpass",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    other_lead_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="otherlead@company.com",
        password_hash="testpass",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@company.com",
        password_hash="testpass",
        user_type=UserType.PM,
        is_active=True,
    )
    other_pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="otherpm@company.com",
        password_hash="testpass",
        user_type=UserType.PM,
        is_active=True,
    )
    admin_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="admin@company.com",
        password_hash="testpass",
        user_type=UserType.ADMIN,
        is_active=True,
    )

    db_session.add_all([emp1_acc, lead_acc, other_lead_acc, pm_acc, other_pm_acc, admin_acc])
    db_session.flush()

    # 3. Employees & PMs
    emp1 = Employee(
        emp_id=1,
        account_id=emp1_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-001",
        full_name="Alice Developer",
        email=emp1_acc.email,
        designation="Software Engineer",
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    lead_emp = Employee(
        emp_id=2,
        account_id=lead_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-002",
        full_name="Carol TeamLead",
        email=lead_acc.email,
        designation="Technical Lead",
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    other_lead_emp = Employee(
        emp_id=3,
        account_id=other_lead_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-003",
        full_name="Oscar OtherLead",
        email=other_lead_acc.email,
        designation="Technical Lead",
        date_of_joining=date(2022, 5, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([emp1, lead_emp, other_lead_emp])
    db_session.flush()

    pm = ProjectManager(
        pm_id=1,
        account_id=pm_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="PM-001",
        full_name="Dave PM",
        email=pm_acc.email,
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    other_pm = ProjectManager(
        pm_id=2,
        account_id=other_pm_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="PM-002",
        full_name="Paul OtherPM",
        email=other_pm_acc.email,
        date_of_joining=date(2022, 3, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([pm, other_pm])
    db_session.flush()

    # 4. Client & Project
    client = Client(
        client_id=1,
        company_name="Acme Corp",
        contact_person="Client Contact",
        email="client@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db_session.add(client)
    db_session.flush()

    proj = Project(
        project_id=1,
        client_id=client.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-WMS",
        name="WMS Enterprise",
        description="Core workflow system",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(proj)
    db_session.flush()

    # 5. Team & Membership
    team = Team(
        team_id=1,
        project_id=proj.project_id,
        lead_emp_id=lead_emp.emp_id,
        name="Backend Core",
        description="Backend development team",
        status=TeamStatus.ACTIVE,
    )
    other_team = Team(
        team_id=2,
        project_id=proj.project_id,
        lead_emp_id=other_lead_emp.emp_id,
        name="Frontend Core",
        description="Frontend development team",
        status=TeamStatus.ACTIVE,
    )
    db_session.add_all([team, other_team])
    db_session.flush()

    tm1 = TeamMember(team_member_id=1, team_id=team.team_id, emp_id=emp1.emp_id)
    tm2 = TeamMember(team_member_id=2, team_id=team.team_id, emp_id=lead_emp.emp_id)
    db_session.add_all([tm1, tm2])
    db_session.flush()

    # 6. Milestone
    milestone = ProjectMilestone(
        id=1,
        project_id=proj.project_id,
        title="Sprint 1 MVP",
        description="Core MVP Milestone",
        target_date=date(2026, 12, 31),
        status=MilestoneStatus.PENDING,
    )
    db_session.add(milestone)
    db_session.flush()

    # 7. Tasks
    task_in_review = Task(
        task_id=10,
        project_id=proj.project_id,
        milestone_id=milestone.id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Develop Authentication Service",
        description="Implement JWT tokens and refresh mechanisms",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_REVIEW,
        progress_pct=80,
    )
    task_sibling = Task(
        task_id=11,
        project_id=proj.project_id,
        milestone_id=milestone.id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Develop Profile Service",
        status=TaskStatus.DONE,
        progress_pct=100,
    )
    task_todo = Task(
        task_id=12,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        title="Todo Task",
        status=TaskStatus.TODO,
    )
    task_in_progress = Task(
        task_id=13,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        title="In Progress Task",
        status=TaskStatus.IN_PROGRESS,
    )
    task_done = Task(
        task_id=14,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        title="Already Done Task",
        status=TaskStatus.DONE,
        progress_pct=100,
    )

    db_session.add_all([task_in_review, task_sibling, task_todo, task_in_progress, task_done])
    db_session.commit()

    # JWT Tokens
    token_emp1 = create_access_token({"sub": str(emp1_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_lead = create_access_token({"sub": str(lead_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_other_lead = create_access_token({"sub": str(other_lead_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_pm = create_access_token({"sub": str(pm_acc.account_id), "type": "access", "role": "PM"})
    token_other_pm = create_access_token({"sub": str(other_pm_acc.account_id), "type": "access", "role": "PM"})
    token_admin = create_access_token({"sub": str(admin_acc.account_id), "type": "access", "role": "ADMIN"})

    return {
        "emp1_acc": emp1_acc,
        "lead_acc": lead_acc,
        "emp1": emp1,
        "lead_emp": lead_emp,
        "milestone": milestone,
        "task_in_review": task_in_review,
        "task_sibling": task_sibling,
        "task_todo": task_todo,
        "task_in_progress": task_in_progress,
        "task_done": task_done,
        "token_emp1": token_emp1,
        "token_lead": token_lead,
        "token_other_lead": token_other_lead,
        "token_pm": token_pm,
        "token_other_pm": token_other_pm,
        "token_admin": token_admin,
    }


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# US-12 Tests
# ==============================================================================

def test_review_task_approve_success(client, test_setup, db_session):
    """Test Team Lead approving a task in IN_REVIEW status."""
    headers = {"Authorization": f"Bearer {test_setup['token_lead']}"}
    payload = {
        "decision": "APPROVE",
        "feedback": "Code approved, unit tests pass with 98% coverage.",
    }

    response = client.put(
        f"/api/v1/tasks/{test_setup['task_in_review'].task_id}/review",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["task_id"] == test_setup["task_in_review"].task_id
    assert data["status"] == "DONE"
    assert data["progress_pct"] == 100
    assert data["completed_at"] is not None
    assert "approved" in data["message"].lower()

    # Verify task in DB
    task = db_session.query(Task).filter(Task.task_id == test_setup["task_in_review"].task_id).first()
    assert task.status == TaskStatus.DONE
    assert task.progress_pct == 100
    assert task.completed_at is not None

    # Verify milestone recalculated to COMPLETED (both task 10 and task 11 are now DONE)
    milestone = db_session.query(ProjectMilestone).filter(ProjectMilestone.id == test_setup["milestone"].id).first()
    assert milestone.status == MilestoneStatus.COMPLETED
    assert milestone.completed_at is not None

    # Verify notification sent to assigned employee
    notif = (
        db_session.query(Notification)
        .filter(Notification.account_id == test_setup["emp1_acc"].account_id, Notification.type == "TASK_APPROVED")
        .first()
    )
    assert notif is not None
    assert "approved" in notif.message.lower()

    # Verify audit log written
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(task.task_id))
        .first()
    )
    assert audit is not None


def test_review_task_reject_success(client, test_setup, db_session):
    """Test Team Lead rejecting a task in IN_REVIEW status with feedback."""
    # Reset task back to IN_REVIEW
    task = test_setup["task_in_review"]
    task.status = TaskStatus.IN_REVIEW
    task.rejection_count = 0
    task.completed_at = None
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_lead']}"}
    payload = {
        "decision": "REJECT",
        "feedback": "Missing error handling for expired tokens in auth router.",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["rejection_feedback"] == "Missing error handling for expired tokens in auth router."
    assert data["rejection_count"] == 1
    assert "rejected" in data["message"].lower()

    # Verify task in DB
    db_session.refresh(task)
    assert task.status == TaskStatus.REJECTED
    assert task.rejection_feedback == "Missing error handling for expired tokens in auth router."
    assert task.rejection_count == 1

    # Verify notification sent to assigned employee
    notif = (
        db_session.query(Notification)
        .filter(Notification.account_id == test_setup["emp1_acc"].account_id, Notification.type == "TASK_REJECTED")
        .first()
    )
    assert notif is not None
    assert "Missing error handling" in notif.message


def test_review_task_multiple_rejections_increment_count(client, test_setup, db_session):
    """Test that consecutive rejections increment rejection_count sequentially."""
    task = test_setup["task_in_review"]
    task.status = TaskStatus.IN_REVIEW
    task.rejection_count = 2
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_lead']}"}
    payload = {
        "decision": "REJECT",
        "feedback": "Third rejection: Unit test coverage still inadequate.",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["rejection_count"] == 3


def test_review_task_reject_without_feedback_422(client, test_setup):
    """Test 422 Unprocessable Entity when rejecting without mandatory feedback."""
    headers = {"Authorization": f"Bearer {test_setup['token_lead']}"}

    # Omitted feedback
    response = client.put(
        f"/api/v1/tasks/{test_setup['task_in_review'].task_id}/review",
        headers=headers,
        json={"decision": "REJECT"},
    )
    assert response.status_code == 422

    # Feedback too short (< 10 chars)
    response_short = client.put(
        f"/api/v1/tasks/{test_setup['task_in_review'].task_id}/review",
        headers=headers,
        json={"decision": "REJECT", "feedback": "Fix this"},
    )
    assert response_short.status_code == 422


@pytest.mark.parametrize("invalid_task_key", ["task_todo", "task_in_progress", "task_done"])
def test_review_task_invalid_status_rejected_400(client, test_setup, invalid_task_key):
    """Test 400 Bad Request when attempting to review a task not in IN_REVIEW status."""
    task = test_setup[invalid_task_key]
    headers = {"Authorization": f"Bearer {test_setup['token_lead']}"}

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 400
    assert "not awaiting review" in response.json()["detail"].lower()


def test_review_task_unauthorized_regular_employee_forbidden_403(client, test_setup):
    """Test 403 Forbidden when a regular employee attempts to review a task."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}

    response = client.put(
        f"/api/v1/tasks/{test_setup['task_in_review'].task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 403


def test_review_task_unrelated_team_lead_forbidden_403(client, test_setup):
    """Test 403 Forbidden when a Team Lead of a different team attempts to review."""
    headers = {"Authorization": f"Bearer {test_setup['token_other_lead']}"}

    response = client.put(
        f"/api/v1/tasks/{test_setup['task_in_review'].task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 403


def test_review_task_project_manager_can_review(client, test_setup, db_session):
    """Test Project Manager of the project can successfully review tasks."""
    task = test_setup["task_in_review"]
    task.status = TaskStatus.IN_REVIEW
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_pm']}"}
    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DONE"


def test_review_task_other_project_manager_forbidden_403(client, test_setup, db_session):
    """Test Project Manager of a different project cannot review."""
    task = test_setup["task_in_review"]
    task.status = TaskStatus.IN_REVIEW
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_other_pm']}"}
    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 403


def test_review_task_admin_can_review(client, test_setup, db_session):
    """Test System Administrator can review any task awaiting review."""
    task = test_setup["task_in_review"]
    task.status = TaskStatus.IN_REVIEW
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_admin']}"}
    response = client.put(
        f"/api/v1/tasks/{task.task_id}/review",
        headers=headers,
        json={"decision": "APPROVE"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DONE"
