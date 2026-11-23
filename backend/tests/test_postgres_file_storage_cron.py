"""Pytest test suite for Scenario S9: Postgres File Storage & Cron Workflows.

Validates:
- US-50 / S9: Files stored in Postgres (stored_file table) rather than ephemeral local disk.
- US-11 / S3: Task attachment persistence, download route, and scoped RBAC.
- US-25 / S7: Executive report database storage, download surviving missing uploads directory.
- US-15 / S5: Scheduled jobs internal endpoint with HMAC token authentication, hidden when unset.
- System health and database connectivity reflecting true DB reachability.
- Production backup endpoints behavior (GitHub Actions mode).
"""
import hashlib
import io
import os
import shutil
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import CommonStatus, PriorityLevel, ProjectStatus, ReportFormat, TaskStatus, TeamStatus, UserType
from app.models.executive_report import ExecutiveReport
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.stored_file import StoredFile
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for each test."""
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
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_setup(db_session):
    """Seed prerequisite test entities: department, accounts, employees, project, team, and tasks."""
    dept = Department(dept_id=1, name="Core Engineering", description="Engineering division")
    db_session.add(dept)

    # User Accounts
    emp1_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="worker@company.com",
        password_hash="testpass",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp2_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="stranger@company.com",
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
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@company.com",
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
    exec_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="exec@company.com",
        password_hash="testpass",
        user_type=UserType.MNC_EXECUTIVE,
        is_active=True,
    )

    db_session.add_all([emp1_acc, emp2_acc, lead_acc, pm_acc, admin_acc, exec_acc])
    db_session.flush()

    # Employees
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
    pm_emp = Employee(
        emp_id=4,
        account_id=pm_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-004",
        full_name="Dave ProjectManager",
        email=pm_acc.email,
        designation="Project Manager",
        date_of_joining=date(2021, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([emp1, emp2, lead_emp, pm_emp])
    db_session.flush()

    # Project Manager & Client
    pm_rec = ProjectManager(
        pm_id=1,
        account_id=pm_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="PM-001",
        full_name="Dave ProjectManager",
        email=pm_acc.email,
        date_of_joining=date(2021, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    client_rec = Client(
        client_id=1,
        company_name="Acme Global",
        contact_person="John Client",
        email="john@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([pm_rec, client_rec])
    db_session.flush()

    # Project
    proj = Project(
        project_id=1,
        client_id=client_rec.client_id,
        pm_id=pm_rec.pm_id,
        project_code="PRJ-S9",
        name="Postgres Storage Initiative",
        description="Migrate file uploads to Postgres and cron jobs to GHA",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(proj)
    db_session.flush()

    # Team & Members
    team = Team(
        team_id=1,
        project_id=proj.project_id,
        lead_emp_id=lead_emp.emp_id,
        name="Platform Core",
        description="Core platform infrastructure",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.flush()

    tm1 = TeamMember(team_member_id=1, team_id=team.team_id, emp_id=emp1.emp_id)
    tm2 = TeamMember(team_member_id=2, team_id=team.team_id, emp_id=lead_emp.emp_id)
    db_session.add_all([tm1, tm2])
    db_session.flush()

    # Task in progress assigned to emp1
    task_in_progress = Task(
        task_id=1,
        project_id=proj.project_id,
        team_id=team.team_id,
        assigned_to=emp1.emp_id,
        created_by=lead_emp.emp_id,
        title="Migrate File Storage to Bytea",
        description="Implement S9 Postgres bytea storage",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    db_session.add(task_in_progress)
    db_session.commit()

    # Access tokens
    token_emp1 = create_access_token({"sub": str(emp1_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_emp2 = create_access_token({"sub": str(emp2_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_lead = create_access_token({"sub": str(lead_acc.account_id), "type": "access", "role": "EMPLOYEE"})
    token_pm = create_access_token({"sub": str(pm_acc.account_id), "type": "access", "role": "PM"})
    token_admin = create_access_token({"sub": str(admin_acc.account_id), "type": "access", "role": "ADMIN"})
    token_exec = create_access_token({"sub": str(exec_acc.account_id), "type": "access", "role": "MNC_EXECUTIVE"})

    return {
        "emp1_acc": emp1_acc,
        "emp2_acc": emp2_acc,
        "lead_acc": lead_acc,
        "pm_acc": pm_acc,
        "admin_acc": admin_acc,
        "exec_acc": exec_acc,
        "emp1": emp1,
        "emp2": emp2,
        "lead_emp": lead_emp,
        "pm_emp": pm_emp,
        "task": task_in_progress,
        "token_emp1": token_emp1,
        "token_emp2": token_emp2,
        "token_lead": token_lead,
        "token_pm": token_pm,
        "token_admin": token_admin,
        "token_exec": token_exec,
    }


def test_submission_file_stored_in_db_and_downloadable(client, test_setup, db_session):
    """Test that task submissions save attachments to stored_file in Postgres and download route serves identical bytes."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    sample_content = b"%PDF-1.4 Mock Deliverable File Content For S9 Testing"
    fake_file = io.BytesIO(sample_content)

    response = client.post(
        f"/api/v1/tasks/{test_setup['task'].task_id}/submit",
        headers=headers,
        data={"remarks": "Submitting task with database attachment"},
        files={"file": ("deliverable_evidence.pdf", fake_file, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    sub_data = response.json()
    submission_id = sub_data["submission_id"]
    assert sub_data["file_name"] == "deliverable_evidence.pdf"
    assert sub_data["file_size_bytes"] == len(sample_content)
    assert sub_data["file_id"] is not None

    # Verify StoredFile row in Postgres
    stored_file = (
        db_session.query(StoredFile)
        .filter(StoredFile.file_id == sub_data["file_id"])
        .first()
    )
    assert stored_file is not None
    assert stored_file.purpose == "TASK_SUBMISSION"
    assert stored_file.filename == "deliverable_evidence.pdf"
    assert stored_file.size_bytes == len(sample_content)
    assert stored_file.sha256 == hashlib.sha256(sample_content).hexdigest()
    assert stored_file.data == sample_content

    # Download route GET /api/v1/tasks/{id}/submissions/{submission_id}/file
    download_url = f"/api/v1/tasks/{test_setup['task'].task_id}/submissions/{submission_id}/file"
    dl_resp = client.get(download_url, headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content == sample_content
    assert 'attachment; filename="deliverable_evidence.pdf"' in dl_resp.headers["content-disposition"]


def test_submission_download_non_latin_filename(client, test_setup, db_session):
    """Test that downloading a file with non-Latin characters (e.g. 报告.pdf) does not 500 (UnicodeEncodeError) and provides ASCII fallback + UTF-8 filename*."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    sample_content = b"%PDF-1.4 Non-Latin Filename Test Deliverable Content"
    fake_file = io.BytesIO(sample_content)

    response = client.post(
        f"/api/v1/tasks/{test_setup['task'].task_id}/submit",
        headers=headers,
        data={"remarks": "Submitting task with non-Latin filename"},
        files={"file": ("报告.pdf", fake_file, "application/pdf")},
    )

    assert response.status_code == 201, response.text
    sub_data = response.json()
    submission_id = sub_data["submission_id"]
    assert sub_data["file_name"] == "报告.pdf"

    # Download route GET /api/v1/tasks/{id}/submissions/{submission_id}/file
    download_url = f"/api/v1/tasks/{test_setup['task'].task_id}/submissions/{submission_id}/file"
    dl_resp = client.get(download_url, headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content == sample_content

    # Check Content-Disposition header format
    cd_header = dl_resp.headers["content-disposition"]
    assert 'attachment; filename="attachment.pdf"' in cd_header
    assert "filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf" in cd_header


def test_submission_upload_size_limit(client, test_setup, monkeypatch):
    """Test that file uploads exceeding MAX_UPLOAD_MB (default 5MB) are rejected with 400 Bad Request."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp1']}"}

    # Default MAX_UPLOAD_MB is 5. We construct 5MB + 100 bytes.
    limit_bytes = settings.max_upload_bytes
    oversized = b"X" * (limit_bytes + 100)
    fake_file = io.BytesIO(oversized)

    response = client.post(
        f"/api/v1/tasks/{test_setup['task'].task_id}/submit",
        headers=headers,
        data={"remarks": "Attempting oversized submission"},
        files={"file": ("large_submission.zip", fake_file, "application/zip")},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert f"{settings.max_upload_mb}MB limit" in detail or "limit" in detail


def test_file_download_scoped(client, test_setup, db_session):
    """Test download route authorization: assignee, TL, PM, and ADMIN allowed; other employees get 403."""
    # 1. Assigned employee submits task
    headers_emp1 = {"Authorization": f"Bearer {test_setup['token_emp1']}"}
    sample_content = b"%PDF-1.4 Scoped Deliverable Test"
    fake_file = io.BytesIO(sample_content)

    sub_resp = client.post(
        f"/api/v1/tasks/{test_setup['task'].task_id}/submit",
        headers=headers_emp1,
        data={"remarks": "Deliverable for scoped test"},
        files={"file": ("scoped.pdf", fake_file, "application/pdf")},
    )
    assert sub_resp.status_code == 201
    submission_id = sub_resp.json()["submission_id"]
    download_url = f"/api/v1/tasks/{test_setup['task'].task_id}/submissions/{submission_id}/file"

    # 2. Assignee -> 200 OK
    resp_assignee = client.get(download_url, headers=headers_emp1)
    assert resp_assignee.status_code == 200
    assert resp_assignee.content == sample_content

    # 3. Team Lead of task's team -> 200 OK
    headers_lead = {"Authorization": f"Bearer {test_setup['token_lead']}"}
    resp_lead = client.get(download_url, headers=headers_lead)
    assert resp_lead.status_code == 200
    assert resp_lead.content == sample_content

    # 4. PM of task's project -> 200 OK
    headers_pm = {"Authorization": f"Bearer {test_setup['token_pm']}"}
    resp_pm = client.get(download_url, headers=headers_pm)
    assert resp_pm.status_code == 200
    assert resp_pm.content == sample_content

    # 5. ADMIN -> 200 OK
    headers_admin = {"Authorization": f"Bearer {test_setup['token_admin']}"}
    resp_admin = client.get(download_url, headers=headers_admin)
    assert resp_admin.status_code == 200
    assert resp_admin.content == sample_content

    # 6. Another employee (Stranger) -> 403 Forbidden
    headers_stranger = {"Authorization": f"Bearer {test_setup['token_emp2']}"}
    resp_stranger = client.get(download_url, headers=headers_stranger)
    assert resp_stranger.status_code == 403
    assert "permission" in resp_stranger.json()["detail"].lower()

    # 7. Non-existent submission -> 404 Not Found
    resp_404_sub = client.get(f"/api/v1/tasks/{test_setup['task'].task_id}/submissions/9999/file", headers=headers_admin)
    assert resp_404_sub.status_code == 404

    # 8. Submission without file -> 404 Not Found
    sub_no_file = TaskSubmission(
        task_id=test_setup["task"].task_id,
        submitted_by=test_setup["emp1"].emp_id,
        remarks="No file attached submission",
        file_id=None,
    )
    db_session.add(sub_no_file)
    db_session.commit()
    resp_no_file = client.get(
        f"/api/v1/tasks/{test_setup['task'].task_id}/submissions/{sub_no_file.submission_id}/file",
        headers=headers_admin,
    )
    assert resp_no_file.status_code == 404


def test_report_download_survives_missing_reports_dir(client, test_setup, tmp_path, monkeypatch):
    """Test that executive reports are stored in stored_file and download succeeds even if uploads/ folder is deleted."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}
    reports_tmp = tmp_path / "uploads" / "reports"
    reports_tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "reports_dir", str(reports_tmp))

    gen_resp = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Survives Disk Deletion Report",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "format": "PDF",
        },
    )
    assert gen_resp.status_code == 201, gen_resp.text
    report_id = gen_resp.json()["report_id"]

    # Delete the entire reports directory to simulate Render ephemeral disk restart / wipe
    shutil.rmtree(reports_tmp, ignore_errors=True)
    assert not os.path.exists(reports_tmp)

    # Download report - must stream from Postgres stored_file and return 200 OK
    dl_resp = client.get(f"/api/v1/executive/reports/{report_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in dl_resp.headers["content-disposition"]
    assert dl_resp.content.startswith(b"%PDF")


def test_job_endpoint_requires_token_and_hidden_when_unset(client, monkeypatch):
    """Test POST /api/v1/internal/jobs/overdue-sweep: returns 404 when unset, requires HMAC token when set."""
    url = "/api/v1/internal/jobs/overdue-sweep"

    # 1. When JOB_TOKEN is unset: route returns 404 (stays hidden)
    monkeypatch.setattr(settings, "job_token", "")
    resp_unset = client.post(url, headers={"X-Job-Token": "some-secret"})
    assert resp_unset.status_code == 404

    # 2. When JOB_TOKEN is configured:
    secret_token = "gha-super-secret-token-12345"
    monkeypatch.setattr(settings, "job_token", secret_token)

    # Missing header -> 401
    resp_no_token = client.post(url)
    assert resp_no_token.status_code == 401

    # Wrong header -> 401
    resp_wrong_token = client.post(url, headers={"X-Job-Token": "wrong-token"})
    assert resp_wrong_token.status_code == 401

    # Non-ASCII header -> 401 (not 500 TypeError / crash)
    resp_non_ascii_token = client.post(url, headers={"X-Job-Token": "token-accentué".encode("latin-1")})
    assert resp_non_ascii_token.status_code == 401

    # Valid header -> 200 OK and returns {flagged, notified}
    resp_valid = client.post(url, headers={"X-Job-Token": secret_token})
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert "flagged" in data
    assert "notified" in data
    assert isinstance(data["flagged"], int)
    assert isinstance(data["notified"], int)


def test_health_returns_503_when_db_down(client, db_session, monkeypatch):
    """Test /health: returns 200 {"status":"healthy","db":"ok"} when DB is up, 503 {"status":"unhealthy","db":"unreachable"} when DB is down."""
    # 1. Normal state: DB healthy
    resp_up = client.get("/health")
    assert resp_up.status_code == 200
    assert resp_up.json() == {"status": "healthy", "db": "ok"}

    # 2. Down state: DB unreachable
    def mock_broken_execute(*args, **kwargs):
        raise RuntimeError("Database connection timed out")

    monkeypatch.setattr(db_session, "execute", mock_broken_execute)

    resp_down = client.get("/health")
    assert resp_down.status_code == 503
    assert resp_down.json() == {"status": "unhealthy", "db": "unreachable"}


def test_production_backup_mode(client, test_setup, monkeypatch):
    """Test that in production ENV, manual backup returns 503 and backup status reports mode: github-actions."""
    headers_admin = {"Authorization": f"Bearer {test_setup['token_admin']}"}
    monkeypatch.setattr(settings, "env", "production")

    # POST /api/v1/admin/backup/trigger returns 503: "Backups run nightly via GitHub Actions"
    trig_resp = client.post("/api/v1/admin/backup/trigger", headers=headers_admin)
    assert trig_resp.status_code == 503
    assert "Backups run nightly via GitHub Actions" in trig_resp.json()["detail"]

    # GET /api/v1/admin/system/backup-status reports mode: "github-actions"
    status_resp = client.get("/api/v1/admin/system/backup-status", headers=headers_admin)
    assert status_resp.status_code == 200
    assert status_resp.json()["mode"] == "github-actions"
