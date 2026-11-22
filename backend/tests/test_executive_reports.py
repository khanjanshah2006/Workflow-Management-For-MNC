"""
Automated Pytest Suite for Executive Management Reports (US-25, S7-BE-2).

Verifies:
1. test_generate_pdf_report_valid_pdf_buffer (starts with %PDF)
2. test_generate_csv_report_correct_headers_and_rows
3. test_metrics_respect_period_boundaries
4. test_invalid_date_range_returns_400 (end < start, range > 366 days, start > today)
5. test_unauthorized_role_rejected_403 (e.g. EMPLOYEE role)
6. test_audit_log_created_on_report_generation (AuditAction.EXPORT on EXECUTIVE_REPORT)
7. test_download_missing_file_returns_404 (nonexistent id, or missing disk file)
8. test_get_reports_history_and_detail (GET /reports, GET /reports/{id})
9. test_download_report_headers (proper Content-Type and Content-Disposition)
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.deliverable import Deliverable, DeliverableFeedback
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    DeliverableStatus,
    FeedbackDecision,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.executive_report import ExecutiveReport
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team
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
def test_setup(db_session, tmp_path, monkeypatch):
    """Seed test entities and isolate reports directory to tmp_path."""
    monkeypatch.setattr(settings, "reports_dir", str(tmp_path))

    # 1. Department
    dept = Department(dept_id=1, name="Core Engineering", description="Engineering division")
    db_session.add(dept)

    # 2. User Accounts
    exec_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="exec@company.com",
        password_hash="fake",
        user_type=UserType.MNC_EXECUTIVE,
        is_active=True,
    )
    admin_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="admin@company.com",
        password_hash="fake",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@company.com",
        password_hash="fake",
        user_type=UserType.PM,
        is_active=True,
    )
    emp_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp@company.com",
        password_hash="fake",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([exec_acc, admin_acc, pm_acc, emp_acc])
    db_session.flush()

    # 3. Project Manager
    pm = ProjectManager(
        pm_id=1,
        account_id=pm_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="PM-001",
        full_name="Dave PM",
        email=pm_acc.email,
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add(pm)

    # 4. Client
    client_corp = Client(
        client_id=1,
        company_name="Acme International",
        contact_person="Client Contact",
        email="contact@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db_session.add(client_corp)
    db_session.flush()

    # 5. Projects
    # Project 1: Active and in scope for Q4-2026 (2026-10-01 to 2026-12-31)
    p1 = Project(
        project_id=1,
        client_id=client_corp.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-ALPHA",
        name="Alpha ERP Modernization",
        description="ERP system overhaul",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=ProjectStatus.ACTIVE,
    )
    # Project 2: Out of scope (ended in 2025 before the period)
    p2_out = Project(
        project_id=2,
        client_id=client_corp.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-OLD",
        name="Legacy System Maintenance",
        description="Completed past project",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 6, 30),
        status=ProjectStatus.COMPLETED,
    )
    db_session.add_all([p1, p2_out])
    db_session.flush()

    # 6. Team
    team1 = Team(
        team_id=1,
        project_id=p1.project_id,
        name="Alpha Core Team",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team1)
    db_session.flush()

    # 7. Milestones for Project 1
    # m1: Due and completed within Q4-2026
    m1 = ProjectMilestone(
        id=1,
        project_id=p1.project_id,
        title="Architecture Milestone",
        target_date=date(2026, 10, 15),
        status=MilestoneStatus.COMPLETED,
        completed_at=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc),
        is_deleted=False,
    )
    # m2: Due in Q4-2026, but not yet completed
    m2 = ProjectMilestone(
        id=2,
        project_id=p1.project_id,
        title="Implementation Milestone",
        target_date=date(2026, 11, 20),
        status=MilestoneStatus.PENDING,
        is_deleted=False,
    )
    # m_future: Outside period (due in 2027)
    m_future = ProjectMilestone(
        id=3,
        project_id=p1.project_id,
        title="Future Delivery",
        target_date=date(2027, 3, 1),
        status=MilestoneStatus.PENDING,
        is_deleted=False,
    )
    db_session.add_all([m1, m2, m_future])
    db_session.flush()

    # 8. Tasks for Project 1
    # t1: Completed inside period
    t1 = Task(
        task_id=1,
        project_id=p1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        title="Database Optimization",
        status=TaskStatus.DONE,
        completed_at=datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc),
    )
    # t2: Overdue task at period end (due 2026-10-05, not completed)
    t2 = Task(
        task_id=2,
        project_id=p1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        title="Security Audit Remediation",
        status=TaskStatus.IN_PROGRESS,
        due_date=date(2026, 10, 5),
    )
    # t_outside: Completed way before reporting period
    t_outside = Task(
        task_id=3,
        project_id=p1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        title="Initial Setup",
        status=TaskStatus.DONE,
        completed_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([t1, t2, t_outside])
    db_session.flush()

    # 9. Deliverables and Feedback for Project 1
    deliv = Deliverable(
        deliverable_id=1,
        project_id=p1.project_id,
        milestone_id=m1.id,
        title="ERP Architecture Blueprint",
        file_url="https://storage.example.com/deliv1.pdf",
        version="1.0",
        status=DeliverableStatus.ACCEPTED,
        submitted_at=datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc),
    )
    db_session.add(deliv)
    db_session.flush()

    fb = DeliverableFeedback(
        feedback_id=1,
        deliverable_id=deliv.deliverable_id,
        given_by_client_id=client_corp.client_id,
        decision=FeedbackDecision.ACCEPTED,
        comments="Excellent architecture document.",
        rating=5,
        given_at=datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc),
    )
    db_session.add(fb)
    db_session.commit()

    # Auth tokens
    token_exec = create_access_token({
        "sub": str(exec_acc.account_id),
        "type": "access",
        "role": "MNC_EXECUTIVE",
    })
    token_admin = create_access_token({
        "sub": str(admin_acc.account_id),
        "type": "access",
        "role": "ADMIN",
    })
    token_emp = create_access_token({
        "sub": str(emp_acc.account_id),
        "type": "access",
        "role": "EMPLOYEE",
    })

    return {
        "exec_acc": exec_acc,
        "admin_acc": admin_acc,
        "emp_acc": emp_acc,
        "token_exec": token_exec,
        "token_admin": token_admin,
        "token_emp": token_emp,
        "project": p1,
        "tmp_path": tmp_path,
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
# US-25 Acceptance Criteria Tests
# ==============================================================================

def test_generate_pdf_report_valid_pdf_buffer(client, test_setup):
    """Verify generating a PDF report writes a valid PDF buffer (starts with %PDF)."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}
    payload = {
        "report_title": "Q4-2026 Executive Performance Review",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "format": "PDF",
        "include_department_breakdown": True,
    }

    response = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["report_title"] == "Q4-2026 Executive Performance Review"
    assert data["format"] == "PDF"
    assert data["include_department_breakdown"] is True
    assert data["file_size_bytes"] > 0
    assert data["download_url"] == f"/api/v1/executive/reports/{data['report_id']}/download"

    # Verify file content on disk starts with %PDF
    report_id = data["report_id"]
    files = list(test_setup["tmp_path"].glob(f"exec_report_{report_id}_*.pdf"))
    assert len(files) == 1
    content = files[0].read_bytes()
    assert content.startswith(b"%PDF")


def test_generate_csv_report_correct_headers_and_rows(client, test_setup):
    """Verify generating a CSV report creates correct headers and project rows."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}
    payload = {
        "report_title": "Q4-2026 Project Metrics Export",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "format": "CSV",
        "include_department_breakdown": False,
    }

    response = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["format"] == "CSV"

    report_id = data["report_id"]
    files = list(test_setup["tmp_path"].glob(f"exec_report_{report_id}_*.csv"))
    assert len(files) == 1

    lines = files[0].read_text(encoding="utf-8").strip().split("\n")
    expected_header = (
        "project_code,project_name,department,status,tasks_completed,"
        "milestones_due,milestones_completed,deliverables_submitted,"
        "deliverables_accepted,avg_client_rating,overdue_tasks_at_period_end"
    )
    assert lines[0] == expected_header
    assert len(lines) >= 2  # Header + in-scope project row
    assert "PRJ-ALPHA,Alpha ERP Modernization,Core Engineering,ACTIVE,1,2,1,1,1,5.00,1" in lines[1]


def test_metrics_respect_period_boundaries(client, test_setup):
    """Verify metric calculations strictly respect period boundaries."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}
    payload = {
        "report_title": "Q4-2026 Boundary Check",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "format": "CSV",
        "include_department_breakdown": False,
    }

    response = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()

    report_id = data["report_id"]
    files = list(test_setup["tmp_path"].glob(f"exec_report_{report_id}_*.csv"))
    csv_text = files[0].read_text(encoding="utf-8")

    # PRJ-OLD ended in 2025 and must not be in this report
    assert "PRJ-OLD" not in csv_text
    # PRJ-ALPHA is in scope
    assert "PRJ-ALPHA" in csv_text


def test_invalid_date_range_returns_400(client, test_setup):
    """Verify business rules rejection (HTTP 400) for invalid date ranges."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}

    # 1. period_end < period_start
    resp_end_before_start = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Invalid End Before Start",
            "period_start": "2026-12-31",
            "period_end": "2026-10-01",
            "format": "PDF",
        },
    )
    assert resp_end_before_start.status_code == 400
    assert "period_end must be greater than or equal to period_start" in resp_end_before_start.json()["detail"]

    # 2. range > 366 days
    resp_too_long = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Range Too Long",
            "period_start": "2025-01-01",
            "period_end": "2026-06-01",
            "format": "PDF",
        },
    )
    assert resp_too_long.status_code == 400
    assert "exceed 366 days" in resp_too_long.json()["detail"]

    # 3. period_start in future
    future_start = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    future_end = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
    resp_future = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Future Report",
            "period_start": future_start,
            "period_end": future_end,
            "format": "PDF",
        },
    )
    assert resp_future.status_code == 400
    assert "future" in resp_future.json()["detail"].lower()


def test_unauthorized_role_rejected_403(client, test_setup):
    """Verify unauthorized roles (such as EMPLOYEE) receive HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {test_setup['token_emp']}"}
    payload = {
        "report_title": "Unauthorized Attempt",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "format": "PDF",
    }

    # Generate
    resp_gen = client.post("/api/v1/executive/reports/generate", headers=headers, json=payload)
    assert resp_gen.status_code == 403

    # History
    resp_list = client.get("/api/v1/executive/reports", headers=headers)
    assert resp_list.status_code == 403

    # Detail
    resp_detail = client.get("/api/v1/executive/reports/1", headers=headers)
    assert resp_detail.status_code == 403


def test_audit_log_created_on_report_generation(client, test_setup, db_session):
    """Verify an AuditLog row with AuditAction.EXPORT is created upon generation."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}
    payload = {
        "report_title": "Audit Checked Report",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "format": "PDF",
    }

    response = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201
    report_id = str(response.json()["report_id"])

    # Query audit log
    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_name == "EXECUTIVE_REPORT",
            AuditLog.entity_ref_id == report_id,
            AuditLog.action == AuditAction.EXPORT,
        )
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.account_id == test_setup["exec_acc"].account_id
    new_val = audit_entry.new_value
    if isinstance(new_val, str):
        import json
        new_val = json.loads(new_val)
    assert new_val["report_title"] == "Audit Checked Report"


def test_download_missing_file_returns_404(client, test_setup, db_session):
    """Verify HTTP 404 when report does not exist or legacy report has missing disk file."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}

    # 1. Nonexistent report ID
    resp_missing_id = client.get("/api/v1/executive/reports/99999/download", headers=headers)
    assert resp_missing_id.status_code == 404

    # 2. In S9, generated reports are stored in DB, so removing file from disk survives (200 OK)
    gen_resp = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "To Be Deleted",
            "period_start": "2026-10-01",
            "period_end": "2026-12-31",
            "format": "PDF",
        },
    )
    report_id = gen_resp.json()["report_id"]

    # Delete file from disk
    files = list(test_setup["tmp_path"].glob(f"exec_report_{report_id}_*.pdf"))
    if files:
        os.remove(files[0])

    resp_survives = client.get(f"/api/v1/executive/reports/{report_id}/download", headers=headers)
    assert resp_survives.status_code == 200
    assert resp_survives.content.startswith(b"%PDF")

    # 3. Legacy report without file_id and missing disk file returns 404
    from app.models.enums import ReportFormat
    legacy_report = ExecutiveReport(
        report_title="Legacy Missing",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 12, 31),
        report_format=ReportFormat.PDF,
        file_path="/nonexistent/path/legacy.pdf",
        file_size_bytes=100,
        file_id=None,
    )
    db_session.add(legacy_report)
    db_session.commit()

    resp_legacy = client.get(f"/api/v1/executive/reports/{legacy_report.report_id}/download", headers=headers)
    assert resp_legacy.status_code == 404


def test_get_reports_history_and_detail(client, test_setup):
    """Verify listing report history (GET /reports) and fetching metadata (GET /reports/{id})."""
    headers = {"Authorization": f"Bearer {test_setup['token_admin']}"}

    # Generate 2 reports
    client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Report Alpha",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "format": "PDF",
        },
    )
    gen2 = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Report Beta",
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
            "format": "CSV",
        },
    )
    r2_id = gen2.json()["report_id"]

    # 1. List reports
    list_resp = client.get("/api/v1/executive/reports?page=1&limit=10", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 2
    assert list_data["items"][0]["report_id"] == r2_id  # Newest first

    # 2. Get single report
    detail_resp = client.get(f"/api/v1/executive/reports/{r2_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["report_title"] == "Report Beta"


def test_download_report_headers(client, test_setup):
    """Verify download endpoint sets correct Content-Type and sanitized Content-Disposition."""
    headers = {"Authorization": f"Bearer {test_setup['token_exec']}"}

    # Generate report
    gen_resp = client.post(
        "/api/v1/executive/reports/generate",
        headers=headers,
        json={
            "report_title": "Q4-2026 Executive Performance Review",
            "period_start": "2026-10-01",
            "period_end": "2026-12-31",
            "format": "PDF",
        },
    )
    report_id = gen_resp.json()["report_id"]

    download_resp = client.get(f"/api/v1/executive/reports/{report_id}/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="Q4-2026_Executive_Performance_Review.pdf"' in download_resp.headers["content-disposition"]
    assert download_resp.content.startswith(b"%PDF")
