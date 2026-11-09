"""
Unit and Integration tests for US-11 (Submit Completed Task).

Acceptance Criteria:
- Only the assigned employee can submit the task (non-assigned employee gets 403 Forbidden).
- Non-employee roles get 403 Forbidden.
- Rejects submission if task is in TODO, IN_REVIEW, DONE, or BLOCKED status (must be IN_PROGRESS) -> 400 Bad Request.
- Validates allowed attachment file formats (.pdf, .zip, .tar.gz, .png, .jpg, .docx) -> 400 for invalid.
- Validates max file size (<= 25MB) -> 400 for oversized files.
- Transitions task status to IN_REVIEW.
- Records submission timestamp and persisted submission record.
- Creates notification for Team Lead ("TASK_SUBMITTED").
- Writes audit log record.
- Chronological ordering of submissions list on GET /api/v1/tasks/{id}/submissions.
- Ordinary employee isolation on GET /api/v1/tasks/{id}/submissions (403 for unauthorized employees).
"""

from datetime import date, datetime, timezone
import io
import os
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
from app.models.enums import CommonStatus, PriorityLevel, ProjectStatus, TaskStatus, TeamStatus, UserType
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task, TaskSubmission
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
        full_name="Alice Worker",
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
        full_name="Bob Stranger",
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
        name="Backend Core",
        description="Backend development team",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.flush()

    tm1 = TeamMember(team_member_id=1, team_id=team.team_id, emp_id=emp1.emp_id)
    tm2 = TeamMember(team_member_id=2, team_id=team.team_id, emp_id=lead_emp.emp_id)
    db_session.add_all([tm1, tm2])
    db_session.flush()

    # 7. Tasks
    task_in_progress = Task(
        task_id=1,
        project_id=proj.project_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Implement Task Submission API",
        description="Develop endpoints and models for task submission",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    task_todo = Task(
        task_id=2,
        project_id=proj.project_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Todo Task",
        status=TaskStatus.TODO,
    )
    task_in_review = Task(
        task_id=3,
        project_id=proj.project_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Already In Review Task",
        status=TaskStatus.IN_REVIEW,
    )
    task_done = Task(
        task_id=4,
        project_id=proj.project_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Done Task",
        status=TaskStatus.DONE,
    )
    task_blocked = Task(
        task_id=5,
        project_id=proj.project_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Blocked Task",
        status=TaskStatus.BLOCKED,
    )

    db_session.add_all([task_in_progress, task_todo, task_in_review, task_done, task_blocked])
    db_session.commit()

    # Create auth tokens
    token_emp1 = create_access_token({"sub": str(emp1_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_emp2 = create_access_token({"sub": str(emp2_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_lead = create_access_token({"sub": str(lead_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_admin = create_access_token({"sub": str(admin_acc.account_id), "type": "access", "role": "ADMIN"})

    return {
        "emp1_acc": emp1_acc,
        "emp2_acc": emp2_acc,
        "lead_acc": lead_acc,
        "admin_acc": admin_acc,
        "emp1": emp1,
        "emp2": emp2,
        "lead_emp": lead_emp,
        "task_in_progress": task_in_progress,
        "task_todo": task_todo,
        "task_in_review": task_in_review,
        "task_done": task_done,
        "task_blocked": task_blocked,
        "token_emp1": token_emp1,
        "token_emp2": token_emp2,
        "token_lead": token_lead,
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
# US-11 Tests
# ==============================================================================

def test_submit_task_success_multipart_with_file(client, test_setup, db_session):
    """Test successful task submission by assigned employee using multipart form-data with file."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    fake_pdf = io.BytesIO(b"%PDF-1.4 sample pdf content deliverable evidence")

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "Completed all unit tests and implementation."},
        files={"file": ("deliverable.pdf", fake_pdf, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["task_id"] == test_setup["task_in_progress"].task_id
    assert data["submitted_by"] == test_setup["emp1"].emp_id
    assert data["remarks"] == "Completed all unit tests and implementation."
    assert data["file_name"] == "deliverable.pdf"
    assert data["file_url"] is not None
    assert data["file_size_bytes"] > 0
    assert "submitted_at" in data

    # Verify task status transitioned to IN_REVIEW
    task = db_session.query(Task).filter(Task.task_id == test_setup["task_in_progress"].task_id).first()
    assert task.status == TaskStatus.IN_REVIEW

    # Verify notification created for Team Lead
    notif = (
        db_session.query(Notification)
        .filter(Notification.account_id == test_setup["lead_acc"].account_id)
        .first()
    )
    assert notif is not None
    assert notif.type == "TASK_SUBMITTED"
    assert "Implement Task Submission API" in notif.message

    # Verify audit log recorded
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(task.task_id))
        .first()
    )
    assert audit is not None


def test_submit_task_success_json_payload(client, test_setup, db_session):
    """Test successful task submission by assigned employee using application/json remarks."""
    # Reset task back to IN_PROGRESS
    task = test_setup["task_in_progress"]
    task.status = TaskStatus.IN_PROGRESS
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    payload = {
        "remarks": "Completed documentation and PR submitted.",
        "file_url": "https://storage.example.com/evidence.zip",
        "file_name": "evidence.zip",
        "file_size_bytes": 1024,
    }

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/submit",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["remarks"] == "Completed documentation and PR submitted."
    assert data["file_url"] == "https://storage.example.com/evidence.zip"
    assert data["file_name"] == "evidence.zip"

    # Verify task status transitioned
    db_session.refresh(task)
    assert task.status == TaskStatus.IN_REVIEW


def test_submit_task_non_assigned_employee_forbidden(client, test_setup):
    """Test 403 Forbidden when an employee attempts to submit a task assigned to someone else."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp2']}"}

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "Attempting to submit another employee's task"},
    )

    assert response.status_code == 403
    assert "Only the employee assigned to this task can submit it" in response.json()["detail"]


def test_submit_task_non_employee_role_forbidden(client, test_setup):
    """Test 403 Forbidden when non-EMPLOYEE role (e.g. ADMIN) attempts to submit."""
    headers = {"Authorization": f"Bearer {test_setup['token_admin']}"}

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "Admin submission attempt"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("invalid_task_key", ["task_todo", "task_in_review", "task_done", "task_blocked"])
def test_submit_task_wrong_status_rejected(client, test_setup, invalid_task_key):
    """Test rejection (400 Bad Request) when submitting tasks not in IN_PROGRESS status."""
    task = test_setup[invalid_task_key]
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/submit",
        headers=headers,
        data={"remarks": "Submitting task in invalid state"},
    )

    assert response.status_code == 400
    assert "Task status must be 'IN_PROGRESS'" in response.json()["detail"]


def test_submit_task_disallowed_file_extension(client, test_setup):
    """Test rejection (400 Bad Request) when attaching disallowed file extension (.exe)."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    fake_exe = io.BytesIO(b"MZ executable content")

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "Submitting malware"},
        files={"file": ("malware.exe", fake_exe, "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]


def test_submit_task_file_too_large(client, test_setup):
    """Test rejection (400 Bad Request) when file exceeds 25MB limit."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    # Create fake in-memory file slightly larger than 25MB: 25 * 1024 * 1024 + 10 bytes
    oversized_bytes = b"0" * (25 * 1024 * 1024 + 10)
    fake_big_file = io.BytesIO(oversized_bytes)

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "Submitting oversized file"},
        files={"file": ("large_archive.zip", fake_big_file, "application/zip")},
    )

    assert response.status_code == 400
    assert "25MB limit" in response.json()["detail"]


def test_submit_task_missing_empty_remarks(client, test_setup):
    """Test rejection (400 Bad Request) when remarks are empty or blank."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}

    response = client.post(
        f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submit",
        headers=headers,
        data={"remarks": "   "},
    )

    assert response.status_code == 400
    assert "Remarks are required" in response.json()["detail"]


def test_get_task_submissions_chronological(client, test_setup, db_session):
    """Test retrieving chronological list of task submissions."""
    task = test_setup["task_in_progress"]
    sub1 = TaskSubmission(
        task_id=task.task_id,
        submitted_by=test_setup["emp1"].emp_id,
        remarks="First revision submission",
        file_name="rev1.pdf",
        submitted_at=datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc),
    )
    sub2 = TaskSubmission(
        task_id=task.task_id,
        submitted_by=test_setup["emp1"].emp_id,
        remarks="Second revision submission with fixes",
        file_name="rev2.pdf",
        submitted_at=datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([sub1, sub2])
    db_session.commit()

    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    response = client.get(f"/api/v1/tasks/{task.task_id}/submissions", headers=headers)

    assert response.status_code == 200, response.text
    submissions = response.json()
    assert len(submissions) >= 2
    assert submissions[0]["remarks"] == "First revision submission"
    assert submissions[1]["remarks"] == "Second revision submission with fixes"


def test_get_task_submissions_isolation_forbidden(client, test_setup):
    """Test 403 Forbidden when unauthorized employee tries to inspect another employee's submissions."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp2']}"}
    response = client.get(f"/api/v1/tasks/{test_setup['task_in_progress'].task_id}/submissions", headers=headers)

    assert response.status_code == 403
    assert "do not have permission" in response.json()["detail"]
