"""
Unit and Integration tests for US-10: Task Progress State Machine & Blocker Tracking.

Acceptance Criteria:
- [ ] Setting status = "BLOCKED" without blocker_reason returns 422 Unprocessable Entity.
- [ ] Setting progress_pct = 100 returns 400 Bad Request (user must submit via review flow).
- [ ] Non-assigned employee attempting update returns 403 Forbidden.
- [ ] Team Lead receives notification when a task is flagged BLOCKED.
- [ ] Pytest test cases in backend/tests/test_task_progress.py pass.
"""

from datetime import date
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditAction, AuditLog
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
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
    """Seed prerequisite test entities: department, accounts, employees, project, team, and tasks."""
    # 1. Department
    dept = Department(dept_id=1, name="Engineering", description="Engineering division")
    db_session.add(dept)

    # 2. User Accounts
    emp1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp1@company.com",
        password_hash="testpass",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp2_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp2@company.com",
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
    admin_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="admin@company.com",
        password_hash="testpass",
        user_type=UserType.ADMIN,
        is_active=True,
    )

    db_session.add_all([emp1_acc, emp2_acc, lead_acc, admin_acc])
    db_session.flush()

    # 3. Employees
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
    emp2 = Employee(
        emp_id=2,
        account_id=emp2_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-002",
        full_name="Bob OtherEmployee",
        email=emp2_acc.email,
        designation="Software Engineer",
        date_of_joining=date(2023, 2, 1),
        status=CommonStatus.ACTIVE,
    )
    lead_emp = Employee(
        emp_id=3,
        account_id=lead_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-003",
        full_name="Carol TeamLead",
        email=lead_acc.email,
        designation="Team Lead",
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([emp1, emp2, lead_emp])
    db_session.flush()

    # 4. Client & Project Manager for project FK
    client = Client(
        client_id=1,
        account_id=None,
        company_name="Acme Corp",
        contact_person="Client Contact",
        email="client@acme.com",
        status=CommonStatus.ACTIVE,
    )
    pm = ProjectManager(
        pm_id=1,
        account_id=None,
        dept_id=dept.dept_id,
        emp_code="PM-001",
        full_name="Dave PM",
        email="pm@company.com",
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([client, pm])
    db_session.flush()

    # 5. Project
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

    # 6. Team & Membership
    team = Team(
        team_id=1,
        project_id=proj.project_id,
        lead_emp_id=lead_emp.emp_id,
        name="Core Backend",
        description="Core development team",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.flush()

    tm1 = TeamMember(team_member_id=1, team_id=team.team_id, emp_id=emp1.emp_id)
    tm2 = TeamMember(team_member_id=2, team_id=team.team_id, emp_id=lead_emp.emp_id)
    db_session.add_all([tm1, tm2])
    db_session.flush()

    # 7. Tasks
    task_active = Task(
        task_id=1,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Implement Task Progress State Machine",
        description="Support IN_PROGRESS and BLOCKED states with blocker tracking",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
        progress_pct=25,
        blocker_reason=None,
    )
    task_blocked = Task(
        task_id=2,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Blocked Task Example",
        description="Blocked awaiting dependency",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.BLOCKED,
        progress_pct=40,
        blocker_reason="Awaiting third-party API credentials",
    )
    db_session.add_all([task_active, task_blocked])
    db_session.commit()

    return {
        "emp1_acc": emp1_acc,
        "emp2_acc": emp2_acc,
        "lead_acc": lead_acc,
        "admin_acc": admin_acc,
        "emp1": emp1,
        "emp2": emp2,
        "lead_emp": lead_emp,
        "team": team,
        "task_active": task_active,
        "task_blocked": task_blocked,
    }


def auth_headers(account: UserAccount) -> dict:
    """Generate authorization header with Bearer token for given account."""
    token = create_access_token(data={"sub": str(account.account_id)})
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Test Cases
# ============================================================================

def test_update_progress_success_in_progress(db_session, test_setup):
    """Assigned employee successfully updates task progress percentage."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    emp1_acc = test_setup["emp1_acc"]
    headers = auth_headers(emp1_acc)

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 50,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["task_id"] == 1
    assert data["status"] == "IN_PROGRESS"
    assert data["progress_pct"] == 50
    assert data["blocker_reason"] is None

    # Check database
    task = db_session.query(Task).filter(Task.task_id == 1).first()
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.progress_pct == 50
    assert task.blocker_reason is None

    app.dependency_overrides.clear()


def test_update_progress_flag_blocked_with_valid_reason_notifies_lead(db_session, test_setup):
    """Flagging task as BLOCKED records blocker reason and triggers TASK_BLOCKED notification to Team Lead."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    emp1_acc = test_setup["emp1_acc"]
    lead_acc = test_setup["lead_acc"]
    headers = auth_headers(emp1_acc)

    blocker_msg = "Awaiting database migration approval from DevOps"
    payload = {
        "status": "BLOCKED",
        "progress_pct": 45,
        "blocker_reason": blocker_msg,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "BLOCKED"
    assert data["progress_pct"] == 45
    assert data["blocker_reason"] == blocker_msg

    # Verify database state
    task = db_session.query(Task).filter(Task.task_id == 1).first()
    assert task.status == TaskStatus.BLOCKED
    assert task.blocker_reason == blocker_msg

    # Verify notification created for Team Lead
    notification = (
        db_session.query(Notification)
        .filter(
            Notification.account_id == lead_acc.account_id,
            Notification.type == "TASK_BLOCKED",
        )
        .first()
    )
    assert notification is not None
    assert "BLOCKED" in notification.message
    assert blocker_msg in notification.message

    app.dependency_overrides.clear()


def test_update_progress_blocked_without_reason_returns_422(db_session, test_setup):
    """Setting status = 'BLOCKED' without a blocker reason (or < 5 chars) returns 422 Unprocessable Entity."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    headers = auth_headers(test_setup["emp1_acc"])

    # 1. Null blocker reason
    res_null = client.put(
        "/api/v1/tasks/1/progress",
        headers=headers,
        json={"status": "BLOCKED", "progress_pct": 30, "blocker_reason": None},
    )
    assert res_null.status_code == 422

    # 2. Empty string
    res_empty = client.put(
        "/api/v1/tasks/1/progress",
        headers=headers,
        json={"status": "BLOCKED", "progress_pct": 30, "blocker_reason": ""},
    )
    assert res_empty.status_code == 422

    # 3. Too short (< 5 chars)
    res_short = client.put(
        "/api/v1/tasks/1/progress",
        headers=headers,
        json={"status": "BLOCKED", "progress_pct": 30, "blocker_reason": "wait"},
    )
    assert res_short.status_code == 422

    app.dependency_overrides.clear()


def test_update_progress_100_percent_rejected_returns_400(db_session, test_setup):
    """Setting progress_pct = 100 returns 400 Bad Request with guidance to submit via review flow."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    headers = auth_headers(test_setup["emp1_acc"])

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 100,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 400
    assert "review" in res.json()["detail"].lower() or "submit" in res.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_update_progress_percentage_bounds(db_session, test_setup):
    """Negative progress or > 100 returns 400 or 422 validation error."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    headers = auth_headers(test_setup["emp1_acc"])

    # Negative
    res_neg = client.put(
        "/api/v1/tasks/1/progress",
        headers=headers,
        json={"status": "IN_PROGRESS", "progress_pct": -5, "blocker_reason": None},
    )
    assert res_neg.status_code in [400, 422]

    # Exceeding 100
    res_over = client.put(
        "/api/v1/tasks/1/progress",
        headers=headers,
        json={"status": "IN_PROGRESS", "progress_pct": 105, "blocker_reason": None},
    )
    assert res_over.status_code in [400, 422]

    app.dependency_overrides.clear()


def test_update_progress_non_assigned_employee_forbidden(db_session, test_setup):
    """Non-assigned employee attempting update returns 403 Forbidden."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # emp2 is not assigned to task 1 and is not team lead
    headers = auth_headers(test_setup["emp2_acc"])

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 50,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_update_progress_team_lead_allowed(db_session, test_setup):
    """Team Lead of the task's team is allowed to update task progress."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Carol is Team Lead of Core Backend team
    headers = auth_headers(test_setup["lead_acc"])

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 60,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["progress_pct"] == 60

    app.dependency_overrides.clear()


def test_update_progress_unblocking_task_clears_blocker_reason(db_session, test_setup):
    """Moving task from BLOCKED back to IN_PROGRESS clears blocker_reason."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    headers = auth_headers(test_setup["emp1_acc"])

    # Task 2 is initially BLOCKED with blocker_reason
    task2 = db_session.query(Task).filter(Task.task_id == 2).first()
    assert task2.status == TaskStatus.BLOCKED
    assert task2.blocker_reason is not None

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 75,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/2/progress", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["progress_pct"] == 75
    assert data["blocker_reason"] is None

    # Check database
    db_session.refresh(task2)
    assert task2.status == TaskStatus.IN_PROGRESS
    assert task2.blocker_reason is None

    app.dependency_overrides.clear()


def test_update_progress_task_not_found(db_session, test_setup):
    """Updating progress on non-existent task returns 404 Not Found."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    headers = auth_headers(test_setup["emp1_acc"])
    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 50,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/99999/progress", headers=headers, json=payload)
    assert res.status_code == 404

    app.dependency_overrides.clear()


def test_update_progress_records_audit_log(db_session, test_setup):
    """Updating progress writes a structured audit log entry."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    emp1_acc = test_setup["emp1_acc"]
    headers = auth_headers(emp1_acc)

    payload = {
        "status": "IN_PROGRESS",
        "progress_pct": 80,
        "blocker_reason": None,
    }

    res = client.put("/api/v1/tasks/1/progress", headers=headers, json=payload)
    assert res.status_code == 200

    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_name == "TASK",
            AuditLog.entity_ref_id == "1",
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.account_id == emp1_acc.account_id,
        )
        .order_by(AuditLog.log_id.desc())
        .first()
    )
    assert audit_entry is not None
    new_val = json.loads(audit_entry.new_value) if isinstance(audit_entry.new_value, str) else audit_entry.new_value
    assert new_val["progress_pct"] == 80
    assert new_val["status"] == "IN_PROGRESS"

    app.dependency_overrides.clear()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["backend/tests/test_task_progress.py", "-v"]))
