"""
Tests for Executive Dashboard & Oversight (US-24, S7).

Verifies:
  - Role-based access control (MNC_EXECUTIVE, ADMIN, SYSTEM_ADMIN authorized; others 403; unauthenticated 401)
  - Milestone velocity calculation accuracy and zero-division safety
  - Delayed project definition criteria (status in {ACTIVE, ON_HOLD} + overdue non-deleted pending milestone)
  - Department attribution via PM's dept_id and the Unassigned bucket fallback
  - Strict PII redaction (no full_name, email, phone, salary, and zero '@' in response)
  - Constant query execution count (<= 8 queries per endpoint, invariant to data volume)
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.executive.service import calculate_milestone_velocity
from app.main import app
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


# ------------------------------------------------------------------
# Fixtures & Helpers
# ------------------------------------------------------------------

class QueryCounter:
    """SQLAlchemy before_cursor_execute statement counter context manager."""

    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.statements = []

    def __enter__(self):
        self.count = 0
        self.statements = []
        event.listen(self.engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.statements.append(statement)


@pytest.fixture
def test_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    try:
        yield {"db": db, "engine": engine, "client": client}
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def _create_user(db, user_type: UserType) -> UserAccount:
    user = UserAccount(
        account_id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@company.com",
        password_hash="hash",
        user_type=user_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_override(user: UserAccount):
    app.dependency_overrides[get_current_user] = lambda: user


def _create_client(db) -> Client:
    c = Client(
        company_name="Acme Corp",
        contact_person="Client Rep",
        email=f"client_{uuid.uuid4().hex[:6]}@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _create_pm(db, dept_id: Optional[int] = None) -> ProjectManager:
    acc = _create_user(db, UserType.PM)
    pm = ProjectManager(
        account_id=acc.account_id,
        dept_id=dept_id,
        emp_code=f"PM_{uuid.uuid4().hex[:6]}",
        full_name="Project Manager",
        email=f"pm_{uuid.uuid4().hex[:6]}@company.com",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


def _create_team(db, project_id: int) -> Team:
    t = Team(
        project_id=project_id,
        name=f"Team {uuid.uuid4().hex[:4]}",
        status=CommonStatus.ACTIVE,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ------------------------------------------------------------------
# Test 1: test_executive_and_admin_roles_authorized
# ------------------------------------------------------------------

def test_executive_and_admin_roles_authorized(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]

    # Seed minimal department
    dept = Department(dept_id=1, name="Cloud Infrastructure", description="Cloud infra")
    db.add(dept)
    db.commit()

    authorized_roles = [
        UserType.MNC_EXECUTIVE,
        UserType.ADMIN,
        UserType.SYSTEM_ADMIN,
    ]

    for role in authorized_roles:
        user = _create_user(db, role)
        _auth_override(user)

        res_overview = client.get("/api/v1/executive/dashboard")
        assert res_overview.status_code == 200, f"Role {role} failed overview with {res_overview.text}"
        data = res_overview.json()
        assert "total_projects" in data
        assert "overall_milestone_velocity_pct" in data

        res_drilldown = client.get("/api/v1/executive/dashboard/departments/1")
        assert res_drilldown.status_code == 200, f"Role {role} failed drilldown with {res_drilldown.text}"
        drill_data = res_drilldown.json()
        assert drill_data["dept_id"] == 1
        assert drill_data["dept_name"] == "Cloud Infrastructure"


# ------------------------------------------------------------------
# Test 2: test_employee_pm_client_forbidden_403
# ------------------------------------------------------------------

def test_employee_pm_client_forbidden_403(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]

    # 1. Unauthenticated request -> 401
    app.dependency_overrides.pop(get_current_user, None)
    res_unauth = client.get("/api/v1/executive/dashboard")
    assert res_unauth.status_code == 401

    res_unauth_dept = client.get("/api/v1/executive/dashboard/departments/1")
    assert res_unauth_dept.status_code == 401

    # 2. Non-executive roles -> 403
    forbidden_roles = [
        UserType.EMPLOYEE,
        UserType.PM,
        UserType.TEAM_LEAD,
        UserType.HR,
        UserType.CLIENT,
        UserType.IT_SUPPORT,
    ]

    for role in forbidden_roles:
        user = _create_user(db, role)
        _auth_override(user)

        res_ov = client.get("/api/v1/executive/dashboard")
        assert res_ov.status_code == 403, f"Role {role} should be forbidden but got {res_ov.status_code}"

        res_dr = client.get("/api/v1/executive/dashboard/departments/1")
        assert res_dr.status_code == 403, f"Role {role} should be forbidden but got {res_dr.status_code}"


# ------------------------------------------------------------------
# Test 3: test_velocity_calculation_accuracy_and_zero_division
# ------------------------------------------------------------------

def test_velocity_calculation_accuracy_and_zero_division(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]

    # Direct unit test of calculate_milestone_velocity helper
    assert calculate_milestone_velocity(0, 0) == 0.0
    assert calculate_milestone_velocity(0, 10) == 0.0
    assert calculate_milestone_velocity(3, 4) == 75.0
    assert calculate_milestone_velocity(1, 3) == 33.3
    assert calculate_milestone_velocity(5, 5) == 100.0

    # API verification with 0 milestones
    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    res = client.get("/api/v1/executive/dashboard")
    assert res.status_code == 200
    assert res.json()["overall_milestone_velocity_pct"] == 0.0


# ------------------------------------------------------------------
# Test 4: test_delayed_project_definition
# ------------------------------------------------------------------

def test_delayed_project_definition(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]
    c = _create_client(db)
    pm = _create_pm(db)

    today = date.today()
    past_date = today - timedelta(days=5)
    future_date = today + timedelta(days=10)

    # 1. Project A: ACTIVE with overdue pending milestone -> DELAYED
    p_a = Project(
        project_id=101, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-A", name="Project A",
        status=ProjectStatus.ACTIVE, start_date=past_date
    )
    m_a = ProjectMilestone(
        id=1, project_id=101, title="M1", target_date=past_date,
        status=MilestoneStatus.PENDING, is_deleted=False
    )

    # 2. Project B: ON_HOLD with overdue pending milestone -> DELAYED
    p_b = Project(
        project_id=102, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-B", name="Project B",
        status=ProjectStatus.ON_HOLD, start_date=past_date
    )
    m_b = ProjectMilestone(
        id=2, project_id=102, title="M2", target_date=past_date,
        status=MilestoneStatus.PENDING, is_deleted=False
    )

    # 3. Project C: ACTIVE with overdue COMPLETED milestone -> NOT delayed
    p_c = Project(
        project_id=103, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-C", name="Project C",
        status=ProjectStatus.ACTIVE, start_date=past_date
    )
    m_c = ProjectMilestone(
        id=3, project_id=103, title="M3", target_date=past_date,
        status=MilestoneStatus.COMPLETED, is_deleted=False
    )

    # 4. Project D: ACTIVE with FUTURE pending milestone -> NOT delayed
    p_d = Project(
        project_id=104, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-D", name="Project D",
        status=ProjectStatus.ACTIVE, start_date=past_date
    )
    m_d = ProjectMilestone(
        id=4, project_id=104, title="M4", target_date=future_date,
        status=MilestoneStatus.PENDING, is_deleted=False
    )

    # 5. Project E: PLANNED with overdue pending milestone -> NOT delayed (must be in ACTIVE/ON_HOLD)
    p_e = Project(
        project_id=105, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-E", name="Project E",
        status=ProjectStatus.PLANNED, start_date=past_date
    )
    m_e = ProjectMilestone(
        id=5, project_id=105, title="M5", target_date=past_date,
        status=MilestoneStatus.PENDING, is_deleted=False
    )

    # 6. Project F: ACTIVE with overdue milestone that is DELETED -> NOT delayed
    p_f = Project(
        project_id=106, client_id=c.client_id, pm_id=pm.pm_id, project_code="PRJ-F", name="Project F",
        status=ProjectStatus.ACTIVE, start_date=past_date
    )
    m_f = ProjectMilestone(
        id=6, project_id=106, title="M6", target_date=past_date,
        status=MilestoneStatus.PENDING, is_deleted=True
    )

    db.add_all([p_a, p_b, p_c, p_d, p_e, p_f, m_a, m_b, m_c, m_d, m_e, m_f])
    db.commit()

    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    res = client.get("/api/v1/executive/dashboard")
    assert res.status_code == 200
    data = res.json()

    # Exactly 2 delayed projects (Project A and Project B)
    assert data["delayed_projects"] == 2
    assert data["total_projects"] == 6
    assert data["active_projects"] == 4


# ------------------------------------------------------------------
# Test 5: test_department_attribution_via_pm_and_unassigned_bucket
# ------------------------------------------------------------------

def test_department_attribution_via_pm_and_unassigned_bucket(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]
    c = _create_client(db)

    # 1. Department 1: Engineering
    dept1 = Department(dept_id=1, name="Engineering", description="Engineering dept")
    db.add(dept1)
    db.commit()

    # 2. PM 1 assigned to Dept 1
    pm1 = _create_pm(db, dept_id=1)

    # 3. PM 2 with NO department (dept_id = None)
    pm2 = _create_pm(db, dept_id=None)

    # Project 1 assigned to PM 1 -> belongs to Engineering
    p1 = Project(
        project_id=1, client_id=c.client_id, pm_id=pm1.pm_id, project_code="P1", name="Project 1",
        status=ProjectStatus.ACTIVE, start_date=date(2026, 1, 1)
    )
    # Project 2 assigned to PM 2 -> belongs to Unassigned
    p2 = Project(
        project_id=2, client_id=c.client_id, pm_id=pm2.pm_id, project_code="P2", name="Project 2",
        status=ProjectStatus.ACTIVE, start_date=date(2026, 1, 1)
    )

    # Employee 1 in Engineering
    emp_acc1 = _create_user(db, UserType.EMPLOYEE)
    emp1 = Employee(
        emp_id=1, account_id=emp_acc1.account_id, dept_id=1,
        emp_code="E01", full_name="Emp One", email="e1@x.com",
        designation="Software Engineer", date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE
    )

    # Employee 2 in Unassigned
    emp_acc2 = _create_user(db, UserType.EMPLOYEE)
    emp2 = Employee(
        emp_id=2, account_id=emp_acc2.account_id, dept_id=None,
        emp_code="E02", full_name="Emp Two", email="e2@x.com",
        designation="QA Engineer", date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE
    )

    db.add_all([p1, p2, emp1, emp2])
    db.commit()

    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    res = client.get("/api/v1/executive/dashboard")
    assert res.status_code == 200
    data = res.json()

    summaries = {s["dept_name"]: s for s in data["department_summaries"]}
    assert "Engineering" in summaries
    assert "Unassigned" in summaries

    # Engineering has 1 project and 1 employee
    assert summaries["Engineering"]["dept_id"] == 1
    assert summaries["Engineering"]["total_projects"] == 1
    assert summaries["Engineering"]["total_employees"] == 1

    # Unassigned has 1 project (P2) and 1 employee (E2)
    assert summaries["Unassigned"]["dept_id"] is None
    assert summaries["Unassigned"]["total_projects"] == 1
    assert summaries["Unassigned"]["total_employees"] == 1


# ------------------------------------------------------------------
# Test 6: test_no_pii_in_response
# ------------------------------------------------------------------

def test_no_pii_in_response(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]
    c = _create_client(db)

    dept = Department(dept_id=1, name="Engineering", description="Eng")
    db.add(dept)
    db.commit()

    pm_acc = _create_user(db, UserType.PM)
    pm = ProjectManager(
        pm_id=1, account_id=pm_acc.account_id, dept_id=1,
        emp_code="PM01", full_name="Alice Confidential", email="alice.secret@company.com",
        phone="+1234567890", date_of_joining=date(2024, 1, 1), status=CommonStatus.ACTIVE
    )
    proj = Project(
        project_id=1, client_id=c.client_id, pm_id=1, project_code="SECURE-01", name="Secret Project",
        status=ProjectStatus.ACTIVE, start_date=date(2026, 1, 1)
    )
    emp_acc = _create_user(db, UserType.EMPLOYEE)
    emp = Employee(
        emp_id=1, account_id=emp_acc.account_id, dept_id=1,
        emp_code="EMP01", full_name="Bob Sensitive", email="bob.confidential@company.com",
        phone="+0987654321", designation="Security Engineer", date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE
    )
    db.add_all([pm, proj, emp])
    db.commit()

    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    # 1. Check Overview endpoint
    res_ov = client.get("/api/v1/executive/dashboard")
    assert res_ov.status_code == 200
    ov_text = res_ov.text

    assert "@" not in ov_text, "Overview response must not contain '@' character"
    assert "full_name" not in ov_text
    assert "Alice Confidential" not in ov_text
    assert "Bob Sensitive" not in ov_text
    assert "phone" not in ov_text
    assert "salary" not in ov_text

    # 2. Check Drilldown endpoint
    res_dr = client.get("/api/v1/executive/dashboard/departments/1")
    assert res_dr.status_code == 200
    dr_text = res_dr.text

    assert "@" not in dr_text, "Drilldown response must not contain '@' character"
    assert "full_name" not in dr_text
    assert "Alice Confidential" not in dr_text
    assert "Bob Sensitive" not in dr_text
    assert "phone" not in dr_text
    assert "salary" not in dr_text


# ------------------------------------------------------------------
# Test 7: test_query_count_constant_with_more_projects
# ------------------------------------------------------------------

def test_query_count_constant_with_more_projects(test_setup):
    db = test_setup["db"]
    engine = test_setup["engine"]
    client = test_setup["client"]
    c = _create_client(db)

    dept = Department(dept_id=1, name="Department 1")
    db.add(dept)
    db.commit()

    pm = _create_pm(db, dept_id=1)

    # Seed initial dataset: 2 projects with teams, milestones & tasks
    for i in range(1, 3):
        p = Project(
            project_id=i, client_id=c.client_id, pm_id=pm.pm_id, project_code=f"PRJ-{i}", name=f"Proj {i}",
            status=ProjectStatus.ACTIVE, start_date=date(2026, 1, 1)
        )
        db.add(p)
        db.commit()
        team = _create_team(db, project_id=i)
        m = ProjectMilestone(
            id=i, project_id=i, title=f"M {i}", target_date=date(2026, 6, 1),
            status=MilestoneStatus.PENDING, is_deleted=False
        )
        t = Task(
            task_id=i, project_id=i, team_id=team.team_id, title=f"T {i}",
            priority=PriorityLevel.MEDIUM, status=TaskStatus.TODO
        )
        db.add_all([m, t])
    db.commit()

    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    # Measure queries for overview with 2 projects
    with QueryCounter(engine) as qc_ov1:
        res1 = client.get("/api/v1/executive/dashboard")
        assert res1.status_code == 200

    count_ov1 = qc_ov1.count
    assert count_ov1 <= 8, f"Overview query count exceeded limit: {count_ov1} > 8"

    # Measure queries for drilldown with 2 projects
    with QueryCounter(engine) as qc_dr1:
        res_dr1 = client.get("/api/v1/executive/dashboard/departments/1")
        assert res_dr1.status_code == 200

    count_dr1 = qc_dr1.count
    assert count_dr1 <= 8, f"Drilldown query count exceeded limit: {count_dr1} > 8"

    # Now scale data significantly: add 15 more projects, teams, tasks, milestones
    for i in range(10, 25):
        p = Project(
            project_id=i, client_id=c.client_id, pm_id=pm.pm_id, project_code=f"SCALE-{i}", name=f"Scale {i}",
            status=ProjectStatus.ACTIVE, start_date=date(2026, 1, 1)
        )
        db.add(p)
        db.commit()
        team = _create_team(db, project_id=i)
        m = ProjectMilestone(
            id=i, project_id=i, title=f"Scale M {i}", target_date=date(2026, 6, 1),
            status=MilestoneStatus.PENDING, is_deleted=False
        )
        t = Task(
            task_id=i, project_id=i, team_id=team.team_id, title=f"Scale T {i}",
            priority=PriorityLevel.MEDIUM, status=TaskStatus.TODO
        )
        db.add_all([m, t])
    db.commit()

    # Measure queries again with scaled data
    db.refresh(user)
    with QueryCounter(engine) as qc_ov2:
        res2 = client.get("/api/v1/executive/dashboard")
        assert res2.status_code == 200

    count_ov2 = qc_ov2.count
    assert count_ov2 == count_ov1, (
        f"Overview query count scaled with data! Was {count_ov1}, now {count_ov2} (must remain constant O(1))"
    )

    db.refresh(user)
    with QueryCounter(engine) as qc_dr2:
        res_dr2 = client.get("/api/v1/executive/dashboard/departments/1")
        assert res_dr2.status_code == 200

    count_dr2 = qc_dr2.count
    assert count_dr2 == count_dr1, (
        f"Drilldown query count scaled with data! Was {count_dr1}, now {count_dr2} (must remain constant O(1))"
    )
    assert count_dr2 == count_dr1, (
        f"Drilldown query count scaled with data! Was {count_dr1}, now {count_dr2} (must remain constant O(1))"
    )


# ------------------------------------------------------------------
# Test 8: test_department_drilldown_not_found_404
# ------------------------------------------------------------------

def test_department_drilldown_not_found_404(test_setup):
    db = test_setup["db"]
    client = test_setup["client"]

    user = _create_user(db, UserType.MNC_EXECUTIVE)
    _auth_override(user)

    res = client.get("/api/v1/executive/dashboard/departments/99999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
