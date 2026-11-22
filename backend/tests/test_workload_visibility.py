"""
Automated test suite for US-35: Workload Visibility Rules.

Requirements:
  1. GET /api/v1/employees/{id}/workload:
     Allowed ONLY for:
       - Self (caller's emp_id == id)
       - HR / HR_MANAGER / ADMIN / SYSTEM_ADMIN
       - PM managing a project the employee is actively (unreleased) staffed on
       - Team Lead of an ACTIVE team the employee belongs to
     Everyone else gets 403 Forbidden.
  2. /projects/{id}/team-workload:
     Remains aggregates only without leaking other projects' task details.
"""
from datetime import date
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
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
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


@pytest.fixture(scope="function")
def db():
    """Isolated in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with overridden DB session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(db, user_type: UserType, email: str | None = None) -> UserAccount:
    acc_id = uuid.uuid4()
    mail = email or f"{acc_id.hex[:8]}@company.com"
    user = UserAccount(
        account_id=acc_id,
        email=mail,
        password_hash="fakehash",
        user_type=user_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_employee(db, user: UserAccount, name: str) -> Employee:
    emp = Employee(
        account_id=user.account_id,
        emp_code=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        designation="Engineer",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def make_pm(db, user: UserAccount, name: str) -> ProjectManager:
    pm = ProjectManager(
        account_id=user.account_id,
        emp_code=f"PM-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


def setup_workload_scenario(db):
    """
    Scenario:
      - Target Employee (emp_target)
      - Managing PM (pm_managing) manages Project 1 (ACTIVE), target employee is staffed (unreleased)
      - Unrelated PM (pm_other) manages Project 2 (ACTIVE), target employee is NOT staffed
      - Team Lead (tl_lead) leads Team 1 (ACTIVE), target employee is a member
      - Unrelated Team Lead (tl_other) leads Team 2 (ACTIVE), target employee is NOT a member
      - Unrelated Employee (emp_unrelated)
      - HR (hr_user)
      - Admin (admin_user)
      - Client (client_user)
    """
    client_user = make_user(db, UserType.CLIENT, "client@corp.com")
    client_rec = Client(
        client_id=1,
        account_id=client_user.account_id,
        company_name="Acme Corp",
        contact_person="John Acme",
        email="client@corp.com",
    )
    db.add(client_rec)
    db.flush()

    hr_user = make_user(db, UserType.HR, "hr@company.com")
    admin_user = make_user(db, UserType.ADMIN, "admin@company.com")

    # Target employee
    target_user = make_user(db, UserType.EMPLOYEE, "target@company.com")
    target_emp = make_employee(db, target_user, "Target Emp")

    # Unrelated employee
    unrelated_user = make_user(db, UserType.EMPLOYEE, "other_emp@company.com")
    unrelated_emp = make_employee(db, unrelated_user, "Unrelated Emp")

    # PMs
    pm_managing_user = make_user(db, UserType.PM, "pm_lead@company.com")
    pm_managing = make_pm(db, pm_managing_user, "Managing PM")

    pm_other_user = make_user(db, UserType.PM, "pm_other@company.com")
    pm_other = make_pm(db, pm_other_user, "Other PM")

    # Projects
    proj1 = Project(
        project_id=1,
        client_id=1,
        pm_id=pm_managing.pm_id,
        project_code="PRJ-ALPHA",
        name="Project Alpha",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    proj2 = Project(
        project_id=2,
        client_id=1,
        pm_id=pm_other.pm_id,
        project_code="PRJ-BETA",
        name="Project Beta",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    db.add_all([proj1, proj2])
    db.flush()

    # Staffing: target employee staffed on Project 1
    asgn1 = ProjectAssignment(
        project_id=1,
        emp_id=target_emp.emp_id,
        role_in_project="Backend Engineer",
        assigned_on=date(2026, 1, 1),
        released_on=None,
    )
    db.add(asgn1)

    # Team Leads
    tl_lead_user = make_user(db, UserType.TEAM_LEAD, "tl_lead@company.com")
    tl_lead_emp = make_employee(db, tl_lead_user, "Lead One")

    tl_other_user = make_user(db, UserType.TEAM_LEAD, "tl_other@company.com")
    tl_other_emp = make_employee(db, tl_other_user, "Lead Other")

    # Teams
    team1 = Team(team_id=1, project_id=1, name="Dev Team 1", lead_emp_id=tl_lead_emp.emp_id, status=TeamStatus.ACTIVE)
    team2 = Team(team_id=2, project_id=2, name="Dev Team 2", lead_emp_id=tl_other_emp.emp_id, status=TeamStatus.ACTIVE)
    db.add_all([team1, team2])
    db.flush()

    tm1 = TeamMember(team_id=1, emp_id=target_emp.emp_id, joined_on=date(2025, 1, 1))
    db.add(tm1)

    # Tasks for target
    task1 = Task(
        task_id=1,
        project_id=1,
        team_id=1,
        assigned_to=target_emp.emp_id,
        title="Active Alpha Task",
        description="Top secret description",
        status=TaskStatus.IN_PROGRESS,
    )
    db.add(task1)
    db.commit()

    return {
        "target_user": target_user,
        "target_emp": target_emp,
        "unrelated_user": unrelated_user,
        "hr_user": hr_user,
        "admin_user": admin_user,
        "pm_managing_user": pm_managing_user,
        "pm_other_user": pm_other_user,
        "tl_lead_user": tl_lead_user,
        "tl_other_user": tl_other_user,
        "client_user": client_user,
        "proj1": proj1,
        "asgn1": asgn1,
    }


def test_workload_visible_only_to_allowed_viewers(client, db):
    """
    US-35: Verifies that only self, HR, Admin, managing PM, and Team Lead
    can view an employee's workload.
    """
    scenario = setup_workload_scenario(db)
    target_id = scenario["target_emp"].emp_id
    url = f"/api/v1/employees/{target_id}/workload"

    # 1. Self -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: scenario["target_user"]
    res_self = client.get(url)
    assert res_self.status_code == 200
    assert res_self.json()["employee_id"] == target_id

    # 2. HR -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: scenario["hr_user"]
    res_hr = client.get(url)
    assert res_hr.status_code == 200

    # 3. Admin -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: scenario["admin_user"]
    res_admin = client.get(url)
    assert res_admin.status_code == 200

    # 4. Managing PM -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: scenario["pm_managing_user"]
    res_pm = client.get(url)
    assert res_pm.status_code == 200

    # 5. Team Lead of employee's active team -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: scenario["tl_lead_user"]
    res_tl = client.get(url)
    assert res_tl.status_code == 200

    # 6. Unrelated regular employee -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: scenario["unrelated_user"]
    res_unrel = client.get(url)
    assert res_unrel.status_code == 403

    # 7. Unrelated PM (manages a different project) -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: scenario["pm_other_user"]
    res_pm_other = client.get(url)
    assert res_pm_other.status_code == 403

    # 8. Unrelated Team Lead (leads a different team) -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: scenario["tl_other_user"]
    res_tl_other = client.get(url)
    assert res_tl_other.status_code == 403

    # 9. Client -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: scenario["client_user"]
    res_client = client.get(url)
    assert res_client.status_code == 403


def test_workload_released_employee_not_visible_to_pm(client, db):
    """
    When an employee is released from a project, the managing PM
    can no longer view their workload (403 Forbidden).
    """
    scenario = setup_workload_scenario(db)
    target_id = scenario["target_emp"].emp_id
    url = f"/api/v1/employees/{target_id}/workload"

    # Release employee from project 1
    scenario["asgn1"].released_on = date(2026, 6, 1)
    db.commit()

    # Managing PM now gets 403
    app.dependency_overrides[get_current_user] = lambda: scenario["pm_managing_user"]
    res = client.get(url)
    assert res.status_code == 403


def test_team_workload_aggregates_only(client, db):
    """
    GET /projects/{id}/team-workload returns aggregates only.
    Confirms no individual task descriptions or titles from other projects appear.
    """
    scenario = setup_workload_scenario(db)
    proj_id = scenario["proj1"].project_id
    url = f"/api/v1/projects/{proj_id}/team-workload"

    # Managing PM views team workload
    app.dependency_overrides[get_current_user] = lambda: scenario["pm_managing_user"]
    res = client.get(url)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1

    item = items[0]
    expected_keys = {
        "emp_id",
        "full_name",
        "role_in_project",
        "open_tasks_in_project",
        "open_tasks_all_projects",
        "active_projects_count",
        "utilization_pct",
    }
    assert set(item.keys()) == expected_keys
    # Ensure sensitive task data does not appear
    res_text = res.text
    assert "Active Alpha Task" not in res_text
    assert "Top secret description" not in res_text
