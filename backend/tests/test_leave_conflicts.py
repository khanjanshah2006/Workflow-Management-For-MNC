"""
Unit and Integration tests for Leave Conflict Detection Engine (US-17, S4-BE-3).

Acceptance Criteria & Test Matrix:
1. Identifying task due dates inside window:
   - Evaluates tasks with status IN (TODO, IN_PROGRESS, BLOCKED, REJECTED)
   - Excludes tasks in DONE or IN_REVIEW
   - Excludes tasks with due_date outside window or null
   - Verifies ordering: due_date ASC, then priority DESC (CRITICAL > HIGH > MEDIUM > LOW)
   - Verifies milestone title population

2. Milestone conflicts in window:
   - Target date in window, is_deleted=False, status=PENDING
   - On staffed projects or projects of conflicting tasks
   - Calculates open_tasks_assigned_to_applicant correctly

3. Teammate workload & availability:
   - Identifies active teammates sharing active team with applicant
   - Flags teammate with approved leave overlapping window as has_leave_overlap=True, unavailable
   - Flags teammate with pending leave overlapping window as has_pending_leave_overlap=True
   - Evaluates active tasks count against threshold

4. Availability threshold system parameter:
   - Reads LEAVE_REASSIGN_MAX_ACTIVE_TASKS from system_parameter (e.g., 2)
   - Falls back to default (5) when parameter is missing

5. Zero conflicts:
   - Returns clean report with has_conflicts=False, empty lists, 200 OK

6. Scope checks (RBAC & Authorization):
   - 404 for non-existent leave request
   - 403 for Team Lead of an unrelated team
   - 403 for Project Manager of an unrelated project
   - 403 for regular employee without lead/PM role
   - 200 for Team Lead of applicant's active team
   - 200 for Project Manager of applicant's active project
   - 200 for HR / HR_MANAGER (global scope)
   - 200 for ADMIN / SYSTEM_ADMIN (global scope)

7. Requests in any status:
   - Can evaluate conflicts for requests in PENDING, APPROVED, REJECTED, CANCELLED
"""

from datetime import date
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    LeaveStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.system_parameter import SystemParameter
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def test_setup():
    """Isolated in-memory SQLite database session and TestClient."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    # 1. Department
    dept = Department(dept_id=1, name="Engineering", description="Engineering Dept")
    db.add(dept)

    # 2. User Accounts
    def make_user(email: str, user_type: UserType) -> UserAccount:
        return UserAccount(
            account_id=uuid.uuid4(),
            email=email,
            password_hash="testpass",
            user_type=user_type,
            is_active=True,
        )

    alice_acc = make_user("alice@company.com", UserType.EMPLOYEE)
    lead_acc = make_user("lead@company.com", UserType.EMPLOYEE)
    other_lead_acc = make_user("otherlead@company.com", UserType.EMPLOYEE)
    bob_acc = make_user("bob@company.com", UserType.EMPLOYEE)
    charlie_acc = make_user("charlie@company.com", UserType.EMPLOYEE)
    pm_acc = make_user("pm@company.com", UserType.PM)
    other_pm_acc = make_user("otherpm@company.com", UserType.PM)
    hr_acc = make_user("hr@company.com", UserType.HR)
    admin_acc = make_user("admin@company.com", UserType.ADMIN)
    dan_acc = make_user("dan@company.com", UserType.EMPLOYEE)

    db.add_all([
        alice_acc, lead_acc, other_lead_acc, bob_acc, charlie_acc,
        pm_acc, other_pm_acc, hr_acc, admin_acc, dan_acc,
    ])
    db.flush()

    # 3. Employees
    def make_emp(emp_id: int, acc: UserAccount, code: str, name: str) -> Employee:
        return Employee(
            emp_id=emp_id,
            account_id=acc.account_id,
            dept_id=dept.dept_id,
            emp_code=code,
            full_name=name,
            email=acc.email,
            designation="Software Engineer",
            date_of_joining=date(2023, 1, 1),
            status=CommonStatus.ACTIVE,
        )

    alice = make_emp(1, alice_acc, "EMP-001", "Alice Developer")
    lead_emp = make_emp(2, lead_acc, "EMP-002", "Carol TeamLead")
    other_lead_emp = make_emp(3, other_lead_acc, "EMP-003", "Oscar OtherLead")
    bob = make_emp(4, bob_acc, "EMP-004", "Bob Teammate")
    charlie = make_emp(5, charlie_acc, "EMP-005", "Charlie Teammate")
    dan = make_emp(7, dan_acc, "EMP-007", "Dan Outsider")

    db.add_all([alice, lead_emp, other_lead_emp, bob, charlie, dan])
    db.flush()

    # 4. Project Managers
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
    db.add_all([pm, other_pm])
    db.flush()

    # 5. Client & Projects
    client_org = Client(
        client_id=1,
        company_name="Acme Corp",
        contact_person="Client Contact",
        email="client@acme.com",
        status=CommonStatus.ACTIVE,
    )
    db.add(client_org)
    db.flush()

    proj1 = Project(
        project_id=1,
        client_id=client_org.client_id,
        pm_id=pm.pm_id,
        project_code="PRJ-001",
        name="WMS Core",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    proj2 = Project(
        project_id=2,
        client_id=client_org.client_id,
        pm_id=other_pm.pm_id,
        project_code="PRJ-002",
        name="Client Portal",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    db.add_all([proj1, proj2])
    db.flush()

    # Project Assignment for Alice on proj1
    pa1 = ProjectAssignment(
        project_id=proj1.project_id,
        emp_id=alice.emp_id,
        role_in_project="Backend Dev",
    )
    db.add(pa1)
    db.flush()

    # 6. Teams & Members
    team1 = Team(
        team_id=1,
        project_id=proj1.project_id,
        lead_emp_id=lead_emp.emp_id,
        name="Backend Team",
        status=TeamStatus.ACTIVE,
    )
    team2 = Team(
        team_id=2,
        project_id=proj2.project_id,
        lead_emp_id=other_lead_emp.emp_id,
        name="Frontend Team",
        status=TeamStatus.ACTIVE,
    )
    db.add_all([team1, team2])
    db.flush()

    # Team members: Alice, lead_emp, bob, charlie are in team1
    # other_lead_emp is in team2
    tm_alice = TeamMember(team_id=team1.team_id, emp_id=alice.emp_id)
    tm_lead = TeamMember(team_id=team1.team_id, emp_id=lead_emp.emp_id)
    tm_bob = TeamMember(team_id=team1.team_id, emp_id=bob.emp_id)
    tm_charlie = TeamMember(team_id=team1.team_id, emp_id=charlie.emp_id)
    tm_other_lead = TeamMember(team_id=team2.team_id, emp_id=other_lead_emp.emp_id)
    db.add_all([tm_alice, tm_lead, tm_bob, tm_charlie, tm_other_lead])
    db.flush()

    # 7. Leave Type & Requests
    leave_type = LeaveType(
        leave_type_id=1,
        name="Annual Leave",
        yearly_quota=20,
        is_paid=True,
    )
    db.add(leave_type)
    db.flush()

    leave_req = LeaveRequest(
        leave_id=1,
        emp_id=alice.emp_id,
        leave_type_id=leave_type.leave_type_id,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 10),
        total_days=8,
        reason="Family vacation",
        status=LeaveStatus.PENDING,
    )
    db.add(leave_req)
    db.commit()

    # JWT Tokens
    def make_token(acc: UserAccount, role: str) -> str:
        return create_access_token({"sub": str(acc.account_id), "type": "access", "role": role})

    tokens = {
        "alice": make_token(alice_acc, "EMPLOYEE"),
        "lead": make_token(lead_acc, "EMPLOYEE"),
        "other_lead": make_token(other_lead_acc, "EMPLOYEE"),
        "bob": make_token(bob_acc, "EMPLOYEE"),
        "charlie": make_token(charlie_acc, "EMPLOYEE"),
        "pm": make_token(pm_acc, "PM"),
        "other_pm": make_token(other_pm_acc, "PM"),
        "hr": make_token(hr_acc, "HR"),
        "admin": make_token(admin_acc, "ADMIN"),
        "dan": make_token(dan_acc, "EMPLOYEE"),
    }

    try:
        yield {
            "db": db,
            "client": client,
            "alice": alice,
            "lead_emp": lead_emp,
            "other_lead_emp": other_lead_emp,
            "bob": bob,
            "charlie": charlie,
            "proj1": proj1,
            "proj2": proj2,
            "team1": team1,
            "team2": team2,
            "leave_req": leave_req,
            "leave_type": leave_type,
            "tokens": tokens,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_conflict_engine_identifies_task_due_dates_inside_window(test_setup):
    """
    US-17: Conflict detection identifies tasks assigned to applicant with status
    in {TODO, IN_PROGRESS, BLOCKED, REJECTED} and due_date in leave window.
    Verifies ordering by due_date ASC, priority DESC (CRITICAL > HIGH > MEDIUM > LOW).
    Verifies milestone_title is populated when attached.
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    alice = test_setup["alice"]
    proj1 = test_setup["proj1"]
    team1 = test_setup["team1"]

    # Create milestone
    ms = ProjectMilestone(
        id=10,
        project_id=proj1.project_id,
        title="Sprint 1 Milestone",
        target_date=date(2026, 6, 15),
        status=MilestoneStatus.PENDING,
    )
    db.add(ms)
    db.flush()

    # Tasks for Alice:
    # 1. Due June 5, Priority HIGH, attached to milestone
    t1 = Task(
        task_id=101,
        project_id=proj1.project_id,
        milestone_id=ms.id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Auth Service",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
        due_date=date(2026, 6, 5),
    )
    # 2. Due June 3, Priority LOW (should be earlier due to date)
    t2 = Task(
        task_id=102,
        project_id=proj1.project_id,
        milestone_id=None,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Database Indexes",
        priority=PriorityLevel.LOW,
        status=TaskStatus.TODO,
        due_date=date(2026, 6, 3),
    )
    # 3. Due June 5, Priority CRITICAL (same due date as t1, but higher priority)
    t3 = Task(
        task_id=103,
        project_id=proj1.project_id,
        milestone_id=None,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Security Hotfix",
        priority=PriorityLevel.CRITICAL,
        status=TaskStatus.BLOCKED,
        due_date=date(2026, 6, 5),
    )
    # 4. Due June 8, Priority MEDIUM, status REJECTED (should be included)
    t4 = Task(
        task_id=104,
        project_id=proj1.project_id,
        milestone_id=None,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Logging Integration",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.REJECTED,
        due_date=date(2026, 6, 8),
    )
    db.add_all([t1, t2, t3, t4])
    db.commit()

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_conflicts"] is True
    assert len(data["conflicting_tasks"]) == 4

    # Verify sort order:
    # 1st: t2 (June 3)
    assert data["conflicting_tasks"][0]["task_id"] == 102
    assert data["conflicting_tasks"][0]["due_date"] == "2026-06-03"

    # 2nd: t3 (June 5, CRITICAL)
    assert data["conflicting_tasks"][1]["task_id"] == 103
    assert data["conflicting_tasks"][1]["priority"] == "CRITICAL"

    # 3rd: t1 (June 5, HIGH) with milestone_title
    assert data["conflicting_tasks"][2]["task_id"] == 101
    assert data["conflicting_tasks"][2]["priority"] == "HIGH"
    assert data["conflicting_tasks"][2]["milestone_title"] == "Sprint 1 Milestone"

    # 4th: t4 (June 8)
    assert data["conflicting_tasks"][3]["task_id"] == 104
    assert data["conflicting_tasks"][3]["status"] == "REJECTED"


def test_conflict_engine_excludes_done_and_in_review_tasks(test_setup):
    """
    US-17: Tasks in DONE or IN_REVIEW, tasks outside the leave window,
    and tasks without due_date are excluded from conflicting_tasks.
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    alice = test_setup["alice"]
    proj1 = test_setup["proj1"]
    team1 = test_setup["team1"]

    # 1. Done task in window -> excluded
    t_done = Task(
        task_id=201,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Completed Feature",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.DONE,
        due_date=date(2026, 6, 5),
    )
    # 2. In Review task in window -> excluded
    t_review = Task(
        task_id=202,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Pending PR Review",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_REVIEW,
        due_date=date(2026, 6, 5),
    )
    # 3. Before window -> excluded
    t_before = Task(
        task_id=203,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Old Task",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
        due_date=date(2026, 5, 25),
    )
    # 4. After window -> excluded
    t_after = Task(
        task_id=204,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Future Task",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.TODO,
        due_date=date(2026, 6, 20),
    )
    # 5. Null due date -> excluded
    t_null_due = Task(
        task_id=205,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Unscheduled Task",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.TODO,
        due_date=None,
    )
    db.add_all([t_done, t_review, t_before, t_after, t_null_due])
    db.commit()

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conflicting_tasks"] == []
    assert data["has_conflicts"] is False


def test_conflict_engine_returns_milestones_in_window(test_setup):
    """
    US-17: Returns pending milestones on applicant projects that target within
    the leave window, along with open_tasks_assigned_to_applicant count.
    Excludes completed, cancelled, deleted milestones, or outside window.
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    alice = test_setup["alice"]
    proj1 = test_setup["proj1"]
    team1 = test_setup["team1"]

    # M1: In window, PENDING -> included
    m1 = ProjectMilestone(
        id=301,
        project_id=proj1.project_id,
        title="Beta Release",
        target_date=date(2026, 6, 6),
        status=MilestoneStatus.PENDING,
        is_deleted=False,
    )
    # M2: In window, COMPLETED -> excluded
    m2 = ProjectMilestone(
        id=302,
        project_id=proj1.project_id,
        title="Alpha Release",
        target_date=date(2026, 6, 3),
        status=MilestoneStatus.COMPLETED,
        is_deleted=False,
    )
    # M3: In window, DELETED -> excluded
    m3 = ProjectMilestone(
        id=303,
        project_id=proj1.project_id,
        title="Scrapped Goal",
        target_date=date(2026, 6, 4),
        status=MilestoneStatus.PENDING,
        is_deleted=True,
    )
    # M4: Outside window -> excluded
    m4 = ProjectMilestone(
        id=304,
        project_id=proj1.project_id,
        title="Final Release",
        target_date=date(2026, 7, 1),
        status=MilestoneStatus.PENDING,
        is_deleted=False,
    )
    db.add_all([m1, m2, m3, m4])
    db.flush()

    # Tasks assigned to Alice on M1
    t1 = Task(
        task_id=311,
        project_id=proj1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Beta Task 1",
        status=TaskStatus.IN_PROGRESS,
    )
    t2 = Task(
        task_id=312,
        project_id=proj1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Beta Task 2",
        status=TaskStatus.TODO,
    )
    t3_done = Task(
        task_id=313,
        project_id=proj1.project_id,
        milestone_id=m1.id,
        team_id=team1.team_id,
        assigned_to=alice.emp_id,
        title="Beta Task Done",
        status=TaskStatus.DONE,
    )
    db.add_all([t1, t2, t3_done])
    db.commit()

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_conflicts"] is True
    assert len(data["milestone_conflicts"]) == 1
    mc = data["milestone_conflicts"][0]
    assert mc["milestone_id"] == 301
    assert mc["title"] == "Beta Release"
    assert mc["target_date"] == "2026-06-06"
    assert mc["open_tasks_assigned_to_applicant"] == 2


def test_conflict_engine_flags_teammate_approved_leave_unavailable(test_setup):
    """
    US-17: Team coverage identifies teammates on shared active teams.
    - Teammate with approved leave overlapping window has has_leave_overlap=True,
      is_available_for_reassignment=False.
    - Teammate with pending leave overlapping window has has_pending_leave_overlap=True.
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    bob = test_setup["bob"]
    charlie = test_setup["charlie"]
    leave_type = test_setup["leave_type"]

    # Bob has approved leave overlapping June 1 - June 10 (e.g., June 4 - June 8)
    bob_leave = LeaveRequest(
        leave_id=2,
        emp_id=bob.emp_id,
        leave_type_id=leave_type.leave_type_id,
        start_date=date(2026, 6, 4),
        end_date=date(2026, 6, 8),
        total_days=5,
        reason="Medical",
        status=LeaveStatus.APPROVED,
    )
    # Charlie has pending leave overlapping June 1 - June 10 (e.g., June 5 - June 7)
    charlie_leave = LeaveRequest(
        leave_id=3,
        emp_id=charlie.emp_id,
        leave_type_id=leave_type.leave_type_id,
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 7),
        total_days=3,
        reason="Personal",
        status=LeaveStatus.PENDING,
    )
    db.add_all([bob_leave, charlie_leave])
    db.commit()

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    coverage_by_id = {item["emp_id"]: item for item in data["team_coverage"]}

    # Bob check
    assert bob.emp_id in coverage_by_id
    assert coverage_by_id[bob.emp_id]["has_leave_overlap"] is True
    assert coverage_by_id[bob.emp_id]["is_available_for_reassignment"] is False

    # Charlie check
    assert charlie.emp_id in coverage_by_id
    assert coverage_by_id[charlie.emp_id]["has_leave_overlap"] is False
    assert coverage_by_id[charlie.emp_id]["has_pending_leave_overlap"] is True
    assert coverage_by_id[charlie.emp_id]["is_available_for_reassignment"] is True


def test_availability_threshold_reads_system_parameter(test_setup):
    """
    US-17: Availability threshold is retrieved from system_parameter
    (LEAVE_REASSIGN_MAX_ACTIVE_TASKS).
    If a teammate's active_tasks_count >= threshold, is_available_for_reassignment=False.
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    bob = test_setup["bob"]
    proj1 = test_setup["proj1"]
    team1 = test_setup["team1"]

    # Set custom parameter: threshold = 2
    param = SystemParameter(
        key="LEAVE_REASSIGN_MAX_ACTIVE_TASKS",
        value="2",
        value_type="integer",
        description="Max active tasks for leave reassignment",
    )
    db.add(param)
    db.flush()

    # Give Bob 2 active tasks
    t1 = Task(
        task_id=401,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=bob.emp_id,
        title="Bob Task 1",
        status=TaskStatus.IN_PROGRESS,
    )
    t2 = Task(
        task_id=402,
        project_id=proj1.project_id,
        team_id=team1.team_id,
        assigned_to=bob.emp_id,
        title="Bob Task 2",
        status=TaskStatus.TODO,
    )
    db.add_all([t1, t2])
    db.commit()

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["availability_threshold"] == 2
    coverage_by_id = {item["emp_id"]: item for item in data["team_coverage"]}
    bob_cov = coverage_by_id[bob.emp_id]
    assert bob_cov["active_tasks_count"] == 2
    # 2 >= 2 => unavailable
    assert bob_cov["is_available_for_reassignment"] is False


def test_zero_conflict_clean_response(test_setup):
    """
    US-17: When no tasks or milestones conflict, returns has_conflicts=False,
    empty arrays, and 200 OK.
    """
    client = test_setup["client"]
    tokens = test_setup["tokens"]

    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["leave_id"] == 1
    assert data["employee_id"] == 1
    assert data["employee_name"] == "Alice Developer"
    assert data["leave_type_name"] == "Annual Leave"
    assert data["status"] == "PENDING"
    assert data["start_date"] == "2026-06-01"
    assert data["end_date"] == "2026-06-10"
    assert data["total_days"] == 8
    assert data["has_conflicts"] is False
    assert data["conflicting_tasks"] == []
    assert data["milestone_conflicts"] == []
    assert len(data["team_coverage"]) >= 1


def test_cross_team_access_rejected_403(test_setup):
    """
    US-17: Team Lead of an unrelated team or PM of an unrelated project
    cannot view conflicts for applicant (403 Forbidden).
    """
    client = test_setup["client"]
    tokens = test_setup["tokens"]

    # Other Team Lead (Oscar)
    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['other_lead']}"},
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

    # Other PM (Paul)
    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['other_pm']}"},
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_nonexistent_request_404(test_setup):
    """
    US-17: Non-existent leave request returns 404 Not Found.
    """
    client = test_setup["client"]
    tokens = test_setup["tokens"]

    resp = client.get(
        "/api/v1/leave/requests/99999/conflicts",
        headers={"Authorization": f"Bearer {tokens['lead']}"},
    )
    assert resp.status_code == 404
    assert "99999 not found" in resp.json()["detail"]


def test_employee_without_lead_role_forbidden_403(test_setup):
    """
    US-17: Regular employees without a lead role in applicant's team
    (or PM role) are rejected with 403 Forbidden.
    """
    client = test_setup["client"]
    tokens = test_setup["tokens"]

    # Dan is a regular employee outside the team
    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['dan']}"},
    )
    assert resp.status_code == 403

    # Alice herself (applicant) cannot review her own conflicts unless she leads a team
    resp = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['alice']}"},
    )
    assert resp.status_code == 403


def test_requests_in_any_status_evaluated_200(test_setup):
    """
    US-17: Reviewers can evaluate conflicts for leave requests in ANY status
    (PENDING, APPROVED, REJECTED, CANCELLED).
    """
    db = test_setup["db"]
    client = test_setup["client"]
    tokens = test_setup["tokens"]
    alice = test_setup["alice"]
    leave_type = test_setup["leave_type"]

    statuses = [
        (LeaveStatus.APPROVED, "APPROVED"),
        (LeaveStatus.REJECTED, "REJECTED"),
        (LeaveStatus.CANCELLED, "CANCELLED"),
    ]

    for req_status, status_str in statuses:
        req = LeaveRequest(
            emp_id=alice.emp_id,
            leave_type_id=leave_type.leave_type_id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
            total_days=5,
            reason=f"Testing {status_str}",
            status=req_status,
        )
        db.add(req)
        db.commit()

        resp = client.get(
            f"/api/v1/leave/requests/{req.leave_id}/conflicts",
            headers={"Authorization": f"Bearer {tokens['lead']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == status_str


def test_global_scope_roles_authorized_200(test_setup):
    """
    US-17: HR and ADMIN accounts have global scope and can view conflicts
    for any leave request without needing to be team lead or PM.
    """
    client = test_setup["client"]
    tokens = test_setup["tokens"]

    # HR Helen
    resp_hr = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['hr']}"},
    )
    assert resp_hr.status_code == 200

    # Admin Adam
    resp_admin = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert resp_admin.status_code == 200

    # Project Manager Dave (managing proj1 where Alice is assigned)
    resp_pm = client.get(
        "/api/v1/leave/requests/1/conflicts",
        headers={"Authorization": f"Bearer {tokens['pm']}"},
    )
    assert resp_pm.status_code == 200
