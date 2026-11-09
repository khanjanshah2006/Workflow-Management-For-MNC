import os
import sys
import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import AuditAction, CommonStatus, PriorityLevel, ProjectStatus, TaskStatus, TeamStatus, UserType
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


@pytest.fixture(scope="function")
def db_session():
    """Create isolated in-memory SQLite database session for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
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
def seed_data(db_session):
    """Seed prerequisite test entities: departments, teams, users, employees, and tasks."""
    dept = Department(dept_id=1, name="Engineering", description="Core software engineering")
    db_session.add(dept)
    db_session.commit()

    client_rec = Client(
        client_id=1,
        company_name="Acme Corp",
        contact_person="Alice Client",
        email="client@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db_session.add(client_rec)
    db_session.commit()

    pm_mgr = ProjectManager(
        pm_id=1,
        emp_code="PM-001",
        full_name="Sarah PM",
        email="pm1@company.com",
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add(pm_mgr)
    db_session.commit()

    proj = Project(
        project_id=1,
        client_id=client_rec.client_id,
        pm_id=pm_mgr.pm_id,
        project_code="PRJ-001",
        name="Apollo MNC Workflow",
        status=ProjectStatus.ACTIVE,
        start_date=date(2026, 1, 1),
    )
    db_session.add(proj)
    db_session.commit()

    # User Accounts
    lead1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="lead1@company.com",
        password_hash="hashed_pw_1",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    lead2_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="lead2@company.com",
        password_hash="hashed_pw_2",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp1@company.com",
        password_hash="hashed_pw_3",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp2_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp2@company.com",
        password_hash="hashed_pw_4",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp_other_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp_other@company.com",
        password_hash="hashed_pw_5",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@company.com",
        password_hash="hashed_pw_6",
        user_type=UserType.PM,
        is_active=True,
    )
    admin_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="admin@company.com",
        password_hash="hashed_pw_7",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    client_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="client@clientcorp.com",
        password_hash="hashed_pw_8",
        user_type=UserType.CLIENT,
        is_active=True,
    )

    for acc in [lead1_acc, lead2_acc, emp1_acc, emp2_acc, emp_other_acc, pm_acc, admin_acc, client_acc]:
        db_session.add(acc)
    db_session.commit()

    # Employees
    lead1_emp = Employee(
        emp_id=1,
        account_id=lead1_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-LEAD-1",
        full_name="Sarah Connor",
        email=lead1_acc.email,
        designation="Team Lead",
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    lead2_emp = Employee(
        emp_id=2,
        account_id=lead2_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-LEAD-2",
        full_name="John Connor",
        email=lead2_acc.email,
        designation="Team Lead",
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    emp1 = Employee(
        emp_id=3,
        account_id=emp1_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-DEV-1",
        full_name="Alice Developer",
        email=emp1_acc.email,
        designation="Senior Software Engineer",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    emp2 = Employee(
        emp_id=4,
        account_id=emp2_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-DEV-2",
        full_name="Bob Tester",
        email=emp2_acc.email,
        designation="QA Engineer",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    emp_other = Employee(
        emp_id=5,
        account_id=emp_other_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-DEV-3",
        full_name="Charlie TeamTwo",
        email=emp_other_acc.email,
        designation="Backend Engineer",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    )

    db_session.add_all([lead1_emp, lead2_emp, emp1, emp2, emp_other])
    db_session.commit()

    # Teams
    team1 = Team(
        team_id=1,
        project_id=proj.project_id,
        lead_emp_id=lead1_emp.emp_id,
        name="Team Alpha",
        description="Alpha development squad",
        status=TeamStatus.ACTIVE,
    )
    team2 = Team(
        team_id=2,
        project_id=proj.project_id,
        lead_emp_id=lead2_emp.emp_id,
        name="Team Beta",
        description="Beta development squad",
        status=TeamStatus.ACTIVE,
    )
    db_session.add_all([team1, team2])
    db_session.commit()

    # Team Members
    tm1 = TeamMember(team_id=team1.team_id, emp_id=emp1.emp_id)
    tm2 = TeamMember(team_id=team1.team_id, emp_id=emp2.emp_id)
    tm3 = TeamMember(team_id=team2.team_id, emp_id=emp_other.emp_id)
    db_session.add_all([tm1, tm2, tm3])
    db_session.commit()

    # Tasks for Team 1
    t1_in_review = Task(
        task_id=1,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Implement Auth Middleware",
        description="Secure JWT authentication endpoints",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_REVIEW,
    )
    t2_in_review = Task(
        task_id=2,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp2.emp_id,
        created_by=lead1_emp.emp_id,
        title="Write QA Regression Suite",
        description="Add automated E2E tests",
        priority=PriorityLevel.LOW,
        status=TaskStatus.IN_REVIEW,
    )
    t3_todo = Task(
        task_id=3,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Setup Redis Cache",
        description="Configure distributed cache",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.TODO,
    )
    t4_in_progress = Task(
        task_id=4,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Migrate Alembic Scripts",
        description="Run database migration scripts",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.IN_PROGRESS,
    )
    t5_rejected = Task(
        task_id=5,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Fix Expired Token Error Handling",
        description="Rejected due to missing regression tests",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.REJECTED,
    )
    t6_rejected_emp2 = Task(
        task_id=6,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp2.emp_id,
        created_by=lead1_emp.emp_id,
        title="Refactor API Gateway Routes",
        description="Rejected due to lint errors",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.REJECTED,
    )
    t7_team2_in_review = Task(
        task_id=7,
        project_id=proj.project_id,
        team_id=team2.team_id,
        assigned_to=emp_other.emp_id,
        created_by=lead2_emp.emp_id,
        title="Team Beta Feature Implementation",
        description="Task belonging to Team Beta",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_REVIEW,
    )
    t8_blocked = Task(
        task_id=8,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Blocked Cloud Migration",
        description="Waiting for infrastructure team",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.BLOCKED,
    )
    t9_done = Task(
        task_id=9,
        project_id=proj.project_id,
        team_id=team1.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead1_emp.emp_id,
        title="Completed DB Indexing",
        description="Database indexing finished",
        priority=PriorityLevel.LOW,
        status=TaskStatus.DONE,
    )

    db_session.add_all([
        t1_in_review, t2_in_review, t3_todo, t4_in_progress,
        t5_rejected, t6_rejected_emp2, t7_team2_in_review, t8_blocked, t9_done
    ])
    db_session.commit()

    # Seed Submissions for Tasks 1 and 2
    sub1 = TaskSubmission(
        task_id=t1_in_review.task_id,
        submitted_by=emp1.emp_id,
        remarks="Initial auth implementation ready for triage",
        file_url="https://storage.company.com/evidence/task-1-v1.zip",
    )
    sub2 = TaskSubmission(
        task_id=t2_in_review.task_id,
        submitted_by=emp2.emp_id,
        remarks="QA suite ready for inspection",
        file_url="https://storage.company.com/evidence/task-2-v1.zip",
    )
    db_session.add_all([sub1, sub2])
    db_session.commit()

    return {
        "dept": dept,
        "project": proj,
        "team1": team1,
        "team2": team2,
        "lead1_acc": lead1_acc,
        "lead2_acc": lead2_acc,
        "emp1_acc": emp1_acc,
        "emp2_acc": emp2_acc,
        "emp_other_acc": emp_other_acc,
        "pm_acc": pm_acc,
        "admin_acc": admin_acc,
        "client_acc": client_acc,
        "lead1_emp": lead1_emp,
        "lead2_emp": lead2_emp,
        "emp1": emp1,
        "emp2": emp2,
        "emp_other": emp_other,
        "t1_in_review": t1_in_review,
        "t2_in_review": t2_in_review,
        "t3_todo": t3_todo,
        "t4_in_progress": t4_in_progress,
        "t5_rejected": t5_rejected,
        "t6_rejected_emp2": t6_rejected_emp2,
        "t7_team2_in_review": t7_team2_in_review,
        "t8_blocked": t8_blocked,
        "t9_done": t9_done,
    }


# ==============================================================================
# 1. Review Queue Tests (GET /api/v1/tasks/review-queue)
# ==============================================================================

def test_review_queue_team_lead_returns_only_in_review_for_own_team(client, seed_data):
    """
    AC 1: GET /review-queue returns only tasks with status == 'IN_REVIEW' belonging to the TL's team.
    Team Lead 1 should see Task 1 and Task 2, but NOT TODO, IN_PROGRESS, REJECTED, or Team 2 tasks.
    """
    response = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["lead1_acc"].account_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    task_ids = [item["task_id"] for item in data]
    assert seed_data["t1_in_review"].task_id in task_ids
    assert seed_data["t2_in_review"].task_id in task_ids
    assert seed_data["t3_todo"].task_id not in task_ids
    assert seed_data["t4_in_progress"].task_id not in task_ids
    assert seed_data["t5_rejected"].task_id not in task_ids
    assert seed_data["t7_team2_in_review"].task_id not in task_ids

    # Verify all tasks have status IN_REVIEW
    for item in data:
        assert item["status"] == "IN_REVIEW"
        assert item["team_id"] == seed_data["team1"].team_id


def test_review_queue_response_fields_schema(client, seed_data):
    """
    Verify response includes assignee name, submission remarks, deliverable file URL, and submission timestamp.
    """
    response = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["lead1_acc"].account_id)},
    )
    assert response.status_code == 200
    data = response.json()

    # Find task 1
    t1_item = next(item for item in data if item["task_id"] == seed_data["t1_in_review"].task_id)
    assert t1_item["title"] == "Implement Auth Middleware"
    assert t1_item["assignee_name"] == "Alice Developer"
    assert t1_item["submission_remarks"] == "Initial auth implementation ready for triage"
    assert t1_item["deliverable_file_url"] == "https://storage.company.com/evidence/task-1-v1.zip"
    assert t1_item["submission_timestamp"] is not None


def test_review_queue_team_isolation(client, seed_data):
    """
    Team Lead 2 queries review queue and should only see Team 2's tasks.
    """
    response = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["lead2_acc"].account_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["task_id"] == seed_data["t7_team2_in_review"].task_id
    assert data[0]["team_id"] == seed_data["team2"].team_id
    assert data[0]["assignee_name"] == "Charlie TeamTwo"


def test_review_queue_priority_filter(client, seed_data):
    """
    Test priority query parameter filtering (e.g. ?priority=HIGH).
    """
    response = client.get(
        "/api/v1/tasks/review-queue?priority=HIGH",
        headers={"X-User-Id": str(seed_data["lead1_acc"].account_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["task_id"] == seed_data["t1_in_review"].task_id
    assert data[0]["priority"] == "HIGH"


def test_review_queue_pagination(client, seed_data):
    """
    Test page and limit pagination parameters.
    """
    # Page 1, limit 1
    resp1 = client.get(
        "/api/v1/tasks/review-queue?page=1&limit=1",
        headers={"X-User-Id": str(seed_data["lead1_acc"].account_id)},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1

    # Page 2, limit 1
    resp2 = client.get(
        "/api/v1/tasks/review-queue?page=2&limit=1",
        headers={"X-User-Id": str(seed_data["lead1_acc"].account_id)},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1

    assert data1[0]["task_id"] != data2[0]["task_id"]


def test_review_queue_allowed_for_pm_and_admin(client, seed_data):
    """
    Allowed Roles: TEAM_LEAD, PM, ADMIN. PM and Admin should be authorized.
    """
    resp_pm = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["pm_acc"].account_id)},
    )
    assert resp_pm.status_code == 200

    resp_admin = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["admin_acc"].account_id)},
    )
    assert resp_admin.status_code == 200


def test_review_queue_forbidden_for_regular_employee_and_client(client, seed_data):
    """
    Regular employees (non-leads) and Client accounts must be rejected with 403 Forbidden.
    """
    resp_emp = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["emp1_acc"].account_id)},
    )
    assert resp_emp.status_code == 403

    resp_client = client.get(
        "/api/v1/tasks/review-queue",
        headers={"X-User-Id": str(seed_data["client_acc"].account_id)},
    )
    assert resp_client.status_code == 403


# ==============================================================================
# 2. Resubmit Task Tests (PUT /api/v1/tasks/{id}/resubmit)
# ==============================================================================

def test_resubmit_success_transitions_status_to_in_review(client, db_session, seed_data):
    """
    AC 3: Resubmitting transitions status from REJECTED back to IN_REVIEW.
    Creates new record in task_submission.
    """
    task = seed_data["t5_rejected"]
    emp_user = seed_data["emp1_acc"]

    payload = {
        "revised_remarks": "Fixed the expired token handling and added 2 regression tests.",
        "new_file_url": "https://storage.company.com/evidence/task-42-rev2.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["task_id"] == task.task_id
    assert res_data["status"] == "IN_REVIEW"
    assert res_data["revised_remarks"] == payload["revised_remarks"]
    assert res_data["new_file_url"] == payload["new_file_url"]

    # Verify in DB: task.status == IN_REVIEW
    db_session.refresh(task)
    assert task.status == TaskStatus.IN_REVIEW

    # Verify new record in task_submission
    sub = (
        db_session.query(TaskSubmission)
        .filter(TaskSubmission.task_id == task.task_id)
        .order_by(TaskSubmission.created_at.desc())
        .first()
    )
    assert sub is not None
    assert sub.remarks == payload["revised_remarks"]
    assert sub.file_url == payload["new_file_url"]
    assert sub.submitted_by == seed_data["emp1"].emp_id


def test_resubmit_notifies_team_lead(client, db_session, seed_data):
    """
    AC 4: Team Lead receives notification upon resubmission.
    Notification type must be 'TASK_RESUBMITTED'.
    """
    task = seed_data["t5_rejected"]
    emp_user = seed_data["emp1_acc"]
    lead1_acc = seed_data["lead1_acc"]

    payload = {
        "revised_remarks": "Updated according to TL comments.",
        "new_file_url": "https://storage.company.com/evidence/task-42-rev3.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert response.status_code == 200

    # Query notifications for lead1
    notif = (
        db_session.query(Notification)
        .filter(Notification.account_id == lead1_acc.account_id, Notification.type == "TASK_RESUBMITTED")
        .first()
    )
    assert notif is not None
    assert "resubmitted" in notif.message.lower()
    assert notif.is_read is False


def test_resubmit_records_audit_log(client, db_session, seed_data):
    """
    Ensure an audit log entry is recorded for state change (API endpoint pattern).
    """
    task = seed_data["t5_rejected"]
    emp_user = seed_data["emp1_acc"]

    payload = {
        "revised_remarks": "Audit verification payload",
        "new_file_url": "https://storage.company.com/evidence/task-42-audit.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert response.status_code == 200

    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(task.task_id))
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.action == AuditAction.UPDATE


def test_resubmit_on_todo_returns_400(client, seed_data):
    """
    AC 2: Attempting to call /resubmit on a TODO task returns 400 Bad Request.
    """
    task = seed_data["t3_todo"]
    emp_user = seed_data["emp1_acc"]

    payload = {
        "revised_remarks": "Attempting resubmit on TODO task",
        "new_file_url": "https://storage.company.com/evidence/invalid.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert response.status_code == 400
    assert "REJECTED" in response.json()["detail"]


def test_resubmit_on_in_progress_returns_400(client, seed_data):
    """
    AC 2: Attempting to call /resubmit on an IN_PROGRESS task returns 400 Bad Request.
    """
    task = seed_data["t4_in_progress"]
    emp_user = seed_data["emp1_acc"]

    payload = {
        "revised_remarks": "Attempting resubmit on IN_PROGRESS task",
        "new_file_url": "https://storage.company.com/evidence/invalid.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert response.status_code == 400
    assert "REJECTED" in response.json()["detail"]


def test_resubmit_on_blocked_or_done_returns_400(client, seed_data):
    """
    Attempting to call /resubmit on BLOCKED or DONE tasks returns 400 Bad Request.
    """
    emp_user = seed_data["emp1_acc"]
    payload = {"revised_remarks": "Testing invalid transitions", "new_file_url": "https://storage.company.com/test.zip"}

    # BLOCKED task
    res_blocked = client.put(
        f"/api/v1/tasks/{seed_data['t8_blocked'].task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert res_blocked.status_code == 400

    # DONE task
    res_done = client.put(
        f"/api/v1/tasks/{seed_data['t9_done'].task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp_user.account_id)},
    )
    assert res_done.status_code == 400


def test_resubmit_forbidden_for_unassigned_employee(client, seed_data):
    """
    Scope Check: task.assigned_to == current_user.emp_id.
    Employee 1 cannot resubmit Task 6 (which is assigned to Employee 2).
    """
    task = seed_data["t6_rejected_emp2"]
    emp1_user = seed_data["emp1_acc"]

    payload = {
        "revised_remarks": "Tampering with coworker's rejected task",
        "new_file_url": "https://storage.company.com/evidence/tamper.zip",
    }

    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json=payload,
        headers={"X-User-Id": str(emp1_user.account_id)},
    )
    assert response.status_code == 403


def test_resubmit_nonexistent_task_returns_404(client, seed_data):
    """
    Attempting to resubmit a non-existent task returns 404 Not Found.
    """
    response = client.put(
        "/api/v1/tasks/999999/resubmit",
        json={"revised_remarks": "Nonexistent", "new_file_url": "https://example.com/file.zip"},
        headers={"X-User-Id": str(seed_data["emp1_acc"].account_id)},
    )
    assert response.status_code == 404


def test_resubmit_forbidden_for_client_role(client, seed_data):
    """
    Client user cannot call resubmit (allowed roles: EMPLOYEE).
    """
    task = seed_data["t5_rejected"]
    response = client.put(
        f"/api/v1/tasks/{task.task_id}/resubmit",
        json={"revised_remarks": "Client attempt", "new_file_url": "https://example.com/file.zip"},
        headers={"X-User-Id": str(seed_data["client_acc"].account_id)},
    )
    assert response.status_code == 403
