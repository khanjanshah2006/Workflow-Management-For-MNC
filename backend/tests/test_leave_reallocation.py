"""
Comprehensive pytest suite for S4 Leave Management – Batch Task Reallocation (US-14, US-19, S4-BE-5).

Covers:
1. test_batch_reassign_updates_assignee_and_notifies_both
2. test_extend_deadline_updates_task_resets_overdue_flag_and_audits
3. test_batch_is_atomic_when_one_action_fails
4. test_cannot_reassign_task_not_owned_by_applicant
5. test_cannot_reassign_to_inactive_or_on_leave_teammate
6. test_pm_cannot_reallocate_tasks_on_other_pm_project
7. Reassignment outside eligible team
8. Reassignment to the applicant
9. Reassignment to teammate with overlapping approved leave
10. Earlier deadline rejection
11. Null current due date
12. Past new due date
13. Pending leave acceptance
14. Approved leave acceptance
15. Rejected and cancelled leave rejection
16. Employee role rejection
17. Team Lead authorization (lead vs non-lead)
18. Admin authorization
19. Duplicate task IDs (422)
20. Empty and oversized batches (422)
21. Warning generation (leave window and milestone target date)
22. Failure during application phase rolls back entire batch
"""
from datetime import date, datetime, timedelta, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.leave.reallocation_router import get_today
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
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
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

TODAY = date(2026, 12, 1)


@pytest.fixture(scope="function")
def db():
    """Create fresh in-memory SQLite database for testing."""
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
    """FastAPI TestClient with overridden get_db and get_today."""
    def override_get_db():
        yield db

    def override_get_today():
        return TODAY

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_today] = override_get_today

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ── Seed Helpers ─────────────────────────────────────────────────────────────

def make_user(db, user_type: UserType, email: str | None = None) -> UserAccount:
    acc_id = uuid.uuid4()
    mail = email or f"{acc_id.hex[:8]}@example.com"
    user = UserAccount(
        account_id=acc_id,
        email=mail,
        password_hash="hashed_pw",
        user_type=user_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_employee(
    db, user: UserAccount, name: str = "Test Emp", status: CommonStatus = CommonStatus.ACTIVE
) -> Employee:
    emp = Employee(
        account_id=user.account_id,
        emp_code=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        designation="Software Engineer",
        date_of_joining=date(2024, 1, 1),
        status=status,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def make_pm(db, user: UserAccount, name: str = "Test PM") -> ProjectManager:
    pm = ProjectManager(
        account_id=user.account_id,
        emp_code=f"PM-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


def make_leave_type(db, name: str = "Annual Leave", quota: int = 20) -> LeaveType:
    lt = LeaveType(name=name, yearly_quota=quota, is_paid=True, is_active=True)
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


def make_leave_request(
    db,
    emp_id: int,
    leave_type_id: int,
    start_date: date,
    end_date: date,
    status: LeaveStatus = LeaveStatus.APPROVED,
) -> LeaveRequest:
    req = LeaveRequest(
        emp_id=emp_id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        total_days=5,
        reason="Vacation leave request for coverage",
        status=status,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def setup_world(db):
    """
    Standard fixture graph:
    - Client 1
    - PM 1 (manages Project 1)
    - PM 2 (manages Project 2)
    - Team Lead 1 (leads Team 1 on Project 1)
    - Team Lead 2 (leads Team 2 on Project 2)
    - Emp 1 (Applicant in Team 1)
    - Emp 2 (Teammate in Team 1)
    - Emp 3 (Outsider in Team 2)
    - Admin user
    - Leave type & approved leave request for Emp 1 [2026-12-05 to 2026-12-12]
    - Task 1: assigned to Emp 1 on Project 1, Team 1 (due 2026-12-08)
    - Task 2: assigned to Emp 1 on Project 1, Team 1 (due 2026-12-09)
    """
    client_rec = Client(company_name="Acme Corp", contact_person="John Doe", email="client@acme.com")
    db.add(client_rec)
    db.commit()
    db.refresh(client_rec)

    # Users
    admin_u = make_user(db, UserType.ADMIN, "admin@example.com")
    pm1_u = make_user(db, UserType.PM, "pm1@example.com")
    pm2_u = make_user(db, UserType.PM, "pm2@example.com")
    tl1_u = make_user(db, UserType.TEAM_LEAD, "tl1@example.com")
    tl2_u = make_user(db, UserType.TEAM_LEAD, "tl2@example.com")
    emp1_u = make_user(db, UserType.EMPLOYEE, "emp1@example.com")
    emp2_u = make_user(db, UserType.EMPLOYEE, "emp2@example.com")
    emp3_u = make_user(db, UserType.EMPLOYEE, "emp3@example.com")

    # Profiles
    pm1 = make_pm(db, pm1_u, "Project Manager 1")
    pm2 = make_pm(db, pm2_u, "Project Manager 2")
    tl1 = make_employee(db, tl1_u, "Team Lead 1")
    tl2 = make_employee(db, tl2_u, "Team Lead 2")
    emp1 = make_employee(db, emp1_u, "Applicant Emp 1")
    emp2 = make_employee(db, emp2_u, "Teammate Emp 2")
    emp3 = make_employee(db, emp3_u, "Outsider Emp 3")

    # Projects
    prj1 = Project(
        client_id=client_rec.client_id,
        pm_id=pm1.pm_id,
        project_code="PRJ-001",
        name="Project One",
        start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    prj2 = Project(
        client_id=client_rec.client_id,
        pm_id=pm2.pm_id,
        project_code="PRJ-002",
        name="Project Two",
        start_date=date(2026, 1, 1),
        status=ProjectStatus.ACTIVE,
    )
    db.add_all([prj1, prj2])
    db.commit()
    db.refresh(prj1)
    db.refresh(prj2)

    # Milestone on Project 1
    ms1 = ProjectMilestone(
        project_id=prj1.project_id,
        title="Sprint 1 Milestone",
        target_date=date(2026, 12, 20),
        status=MilestoneStatus.PENDING,
    )
    db.add(ms1)
    db.commit()
    db.refresh(ms1)

    # Teams
    team1 = Team(
        project_id=prj1.project_id,
        lead_emp_id=tl1.emp_id,
        name="Team Alpha",
        status=TeamStatus.ACTIVE,
    )
    team2 = Team(
        project_id=prj2.project_id,
        lead_emp_id=tl2.emp_id,
        name="Team Beta",
        status=TeamStatus.ACTIVE,
    )
    db.add_all([team1, team2])
    db.commit()
    db.refresh(team1)
    db.refresh(team2)

    # Team Members
    db.add_all([
        TeamMember(team_id=team1.team_id, emp_id=tl1.emp_id),
        TeamMember(team_id=team1.team_id, emp_id=emp1.emp_id),
        TeamMember(team_id=team1.team_id, emp_id=emp2.emp_id),
        TeamMember(team_id=team2.team_id, emp_id=tl2.emp_id),
        TeamMember(team_id=team2.team_id, emp_id=emp3.emp_id),
    ])
    db.commit()

    # Leave type & Leave Request for Emp 1
    lt = make_leave_type(db, "Annual Leave", 20)
    leave_req = make_leave_request(
        db,
        emp_id=emp1.emp_id,
        leave_type_id=lt.leave_type_id,
        start_date=date(2026, 12, 5),
        end_date=date(2026, 12, 12),
        status=LeaveStatus.APPROVED,
    )

    # Tasks for Emp 1
    t1 = Task(
        project_id=prj1.project_id,
        team_id=team1.team_id,
        milestone_id=ms1.id,
        assigned_to=emp1.emp_id,
        title="Develop Authentication Service",
        priority=PriorityLevel.HIGH,
        status=TaskStatus.IN_PROGRESS,
        start_date=date(2026, 12, 1),
        due_date=date(2026, 12, 8),
        overdue_notified_at=datetime.now(timezone.utc),
    )
    t2 = Task(
        project_id=prj1.project_id,
        team_id=team1.team_id,
        milestone_id=ms1.id,
        assigned_to=emp1.emp_id,
        title="Write API Documentation",
        priority=PriorityLevel.MEDIUM,
        status=TaskStatus.TODO,
        start_date=date(2026, 12, 1),
        due_date=date(2026, 12, 9),
    )
    db.add_all([t1, t2])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)

    return {
        "admin_u": admin_u,
        "pm1_u": pm1_u,
        "pm2_u": pm2_u,
        "tl1_u": tl1_u,
        "tl2_u": tl2_u,
        "emp1_u": emp1_u,
        "emp2_u": emp2_u,
        "emp3_u": emp3_u,
        "tl1": tl1,
        "emp1": emp1,
        "emp2": emp2,
        "emp3": emp3,
        "prj1": prj1,
        "prj2": prj2,
        "team1": team1,
        "team2": team2,
        "milestone": ms1,
        "leave_type": lt,
        "leave_req": leave_req,
        "task1": t1,
        "task2": t2,
    }


# ── Required Tests ────────────────────────────────────────────────────────────

def test_batch_reassign_updates_assignee_and_notifies_both(client, db):
    """
    Test 1: Batch reassignment updates task assignee, sends TASK_ASSIGNED to new assignee,
    sends TASK_REASSIGNED to old assignee, and creates an UPDATE audit record with leave_id.
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reassigned for sprint coverage during approved annual leave.",
            }
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["leave_id"] == w["leave_req"].leave_id
    assert data["reallocated_count"] == 1
    assert len(data["reassigned"]) == 1
    assert data["reassigned"][0] == {
        "task_id": w["task1"].task_id,
        "from_emp_id": w["emp1"].emp_id,
        "to_emp_id": w["emp2"].emp_id,
    }

    # Verify task updated in DB
    db.refresh(w["task1"])
    assert w["task1"].assigned_to == w["emp2"].emp_id

    # Verify notifications
    notes_new = db.query(Notification).filter(Notification.account_id == w["emp2_u"].account_id).all()
    assert any(n.type == "TASK_ASSIGNED" and f"#{w['task1'].task_id}" in n.message for n in notes_new)

    notes_old = db.query(Notification).filter(Notification.account_id == w["emp1_u"].account_id).all()
    assert any(n.type == "TASK_REASSIGNED" and f"#{w['task1'].task_id}" in n.message for n in notes_old)

    # Verify AuditLog
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(w["task1"].task_id))
        .first()
    )
    assert audit is not None
    assert audit.action == AuditAction.UPDATE
    assert '"leave_id": ' + str(w["leave_req"].leave_id) in audit.new_value
    assert '"action_type": "REASSIGN"' in audit.new_value
    assert "Reassigned for sprint coverage" in audit.new_value


def test_extend_deadline_updates_task_resets_overdue_flag_and_audits(client, db):
    """
    Test 2: EXTEND_DEADLINE updates due_date, resets overdue_notified_at to None,
    notifies current assignee with TASK_DEADLINE_EXTENDED, and creates audit log.
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["pm1_u"]

    assert w["task1"].overdue_notified_at is not None

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-18",
                "reason": "Deadline extended to accommodate approved leave coverage.",
            }
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["reallocated_count"] == 1
    assert len(data["extended"]) == 1
    assert data["extended"][0]["old_due_date"] == "2026-12-08"
    assert data["extended"][0]["new_due_date"] == "2026-12-18"

    # Verify task updated in DB
    db.refresh(w["task1"])
    assert str(w["task1"].due_date) == "2026-12-18"
    assert w["task1"].overdue_notified_at is None

    # Verify notification
    notes = db.query(Notification).filter(Notification.account_id == w["emp1_u"].account_id).all()
    assert any(n.type == "TASK_DEADLINE_EXTENDED" and f"#{w['task1'].task_id}" in n.message for n in notes)

    # Verify AuditLog
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(w["task1"].task_id))
        .first()
    )
    assert audit is not None
    assert audit.action == AuditAction.UPDATE
    assert '"leave_id": ' + str(w["leave_req"].leave_id) in audit.new_value
    assert '"action_type": "EXTEND_DEADLINE"' in audit.new_value
    assert "Deadline extended" in audit.new_value


def test_batch_is_atomic_when_one_action_fails(client, db):
    """
    Test 3: If any action in batch fails validation, NO task changes, audit entries,
    or notifications are persisted.
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Action 1 is valid, Action 2 is invalid (extend to an earlier date)
    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reassigning task 1 for coverage during leave.",
            },
            {
                "task_id": w["task2"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-02",  # Current is 2026-12-09 -> earlier!
                "reason": "Invalid extension date that should fail validation.",
            },
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert "New due date must be after current due date" in res.json()["detail"]
    assert res.json()["task_id"] == w["task2"].task_id

    # Verify task 1 was NOT modified
    db.refresh(w["task1"])
    assert w["task1"].assigned_to == w["emp1"].emp_id

    # Verify no notifications and no audit logs created
    notes = db.query(Notification).all()
    assert len(notes) == 0
    audits = db.query(AuditLog).filter(AuditLog.entity_name == "TASK").all()
    assert len(audits) == 0


def test_cannot_reassign_task_not_owned_by_applicant(client, db):
    """
    Test 4: Cannot reallocate a task that is not assigned to the leave applicant (400).
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Create a task assigned to Emp 2 instead of Emp 1
    other_task = Task(
        project_id=w["prj1"].project_id,
        team_id=w["team1"].team_id,
        assigned_to=w["emp2"].emp_id,
        title="Other teammate's task",
        status=TaskStatus.TODO,
        due_date=date(2026, 12, 10),
    )
    db.add(other_task)
    db.commit()
    db.refresh(other_task)

    payload = {
        "actions": [
            {
                "task_id": other_task.task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp1"].emp_id,
                "reason": "Attempting to reassign task not owned by applicant.",
            }
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Task not assigned to leave applicant"
    assert res.json()["task_id"] == other_task.task_id


def test_cannot_reassign_to_inactive_or_on_leave_teammate(client, db):
    """
    Test 5: Cannot reassign to an inactive employee (400 "Assignee not in team")
    or to an employee with an approved overlapping leave (400 "Assignee is on leave during this period").
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Case A: Inactive teammate
    inactive_u = make_user(db, UserType.EMPLOYEE, "inactive@example.com")
    inactive_emp = make_employee(db, inactive_u, "Inactive Dev", status=CommonStatus.INACTIVE)
    db.add(TeamMember(team_id=w["team1"].team_id, emp_id=inactive_emp.emp_id))
    db.commit()

    payload_inactive = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": inactive_emp.emp_id,
                "reason": "Reassigning to inactive member should be rejected.",
            }
        ]
    }
    res_inact = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload_inactive)
    assert res_inact.status_code == 400
    assert res_inact.json()["detail"] == "Assignee not in team"
    assert res_inact.json()["task_id"] == w["task1"].task_id

    # Case B: Approved overlapping leave on new assignee
    # Leave applicant's leave is 2026-12-05 to 2026-12-12
    # Create approved leave for Emp 2 overlapping [2026-12-10 to 2026-12-15]
    make_leave_request(
        db,
        emp_id=w["emp2"].emp_id,
        leave_type_id=w["leave_type"].leave_type_id,
        start_date=date(2026, 12, 10),
        end_date=date(2026, 12, 15),
        status=LeaveStatus.APPROVED,
    )

    payload_overlap = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reassigning to teammate with overlapping leave.",
            }
        ]
    }
    res_overlap = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload_overlap)
    assert res_overlap.status_code == 400
    assert res_overlap.json()["detail"] == "Assignee is on leave during this period"
    assert res_overlap.json()["task_id"] == w["task1"].task_id


def test_pm_cannot_reallocate_tasks_on_other_pm_project(client, db):
    """
    Test 6: PM can only reallocate tasks for projects they manage.
    PM2 cannot reallocate task 1 on Project 1 (managed by PM1).
    """
    w = setup_world(db)
    # PM 2 tries to reallocate task 1 on Project 1
    app.dependency_overrides[get_current_user] = lambda: w["pm2_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "PM 2 trying to manage PM 1 project task.",
            }
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 403


# ── Additional Specific Requirements ──────────────────────────────────────────

def test_reassignment_outside_eligible_team(client, db):
    """Reassigning to an active employee who is not on the task's team returns 400 'Assignee not in team'."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["admin_u"]

    # Emp 3 is in Team 2, Task 1 is in Team 1
    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp3"].emp_id,
                "reason": "Reassigning outside team should fail eligibility.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Assignee not in team"
    assert res.json()["task_id"] == w["task1"].task_id


def test_reassignment_to_applicant(client, db):
    """Cannot reassign task back to the leave applicant (400)."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp1"].emp_id,
                "reason": "Cannot reassign to the leave applicant themselves.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert "Cannot reassign" in res.json()["detail"]
    assert res.json()["task_id"] == w["task1"].task_id


def test_earlier_or_equal_deadline_rejection(client, db):
    """New due date earlier than or equal to current due date returns 400."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Current due date is 2026-12-08
    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-08",
                "reason": "Same date extension must be rejected.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert "New due date must be after current due date" in res.json()["detail"]
    assert res.json()["task_id"] == w["task1"].task_id


def test_null_current_due_date(client, db):
    """Task without a current due date cannot have its deadline extended (400)."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    w["task1"].due_date = None
    db.commit()

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "Extending deadline on task with null due date.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Task has no current due date"
    assert res.json()["task_id"] == w["task1"].task_id


def test_past_new_due_date(client, db):
    """New due date in the past (< today) returns 400."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Task start_date and due_date set to past
    w["task1"].start_date = date(2026, 11, 10)
    w["task1"].due_date = date(2026, 11, 20)
    db.commit()

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-11-25",  # Earlier than TODAY (2026-12-01)
                "reason": "Past date extension must be rejected.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert "New due date cannot be in the past" in res.json()["detail"]
    assert res.json()["task_id"] == w["task1"].task_id


def test_pending_leave_acceptance(client, db):
    """PENDING leave request is eligible for task reallocation (200)."""
    w = setup_world(db)
    w["leave_req"].status = LeaveStatus.PENDING
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reallocation on pending leave request.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200
    assert res.json()["reallocated_count"] == 1


def test_approved_leave_acceptance(client, db):
    """APPROVED leave request is eligible for task reallocation (200)."""
    w = setup_world(db)
    w["leave_req"].status = LeaveStatus.APPROVED
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reallocation on approved leave request.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200
    assert res.json()["reallocated_count"] == 1


def test_rejected_and_cancelled_leave_rejection(client, db):
    """REJECTED and CANCELLED leave requests are rejected with 400 'Leave request is not active'."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Reallocation should fail for inactive leave.",
            }
        ]
    }

    # REJECTED
    w["leave_req"].status = LeaveStatus.REJECTED
    db.commit()
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Leave request is not active"

    # CANCELLED
    w["leave_req"].status = LeaveStatus.CANCELLED
    db.commit()
    res2 = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res2.status_code == 400
    assert res2.json()["detail"] == "Leave request is not active"


def test_employee_role_rejection(client, db):
    """Standard EMPLOYEE role without lead privileges cannot access the endpoint (403)."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["emp2_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "Standard employee trying to reallocate tasks.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 403


def test_team_lead_authorization(client, db):
    """
    TEAM_LEAD leading the applicant's active team is allowed (200).
    TEAM_LEAD of another team not containing applicant is rejected (403).
    """
    w = setup_world(db)

    # Lead 1 leads applicant's team -> 200
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]
    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "Team lead extending deadline for member.",
            }
        ]
    }
    res1 = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res1.status_code == 200

    # Lead 2 does NOT lead applicant's team -> 403
    app.dependency_overrides[get_current_user] = lambda: w["tl2_u"]
    res2 = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res2.status_code == 403


def test_admin_authorization(client, db):
    """ADMIN can reallocate tasks across any team and project (200)."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["admin_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Admin reassigning task across project teams.",
            }
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200


def test_duplicate_task_ids_rejected(client, db):
    """Batch containing duplicate task IDs is rejected with 422."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "First action for task 1 coverage.",
            },
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "Duplicate action on same task 1.",
            },
        ]
    }
    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 422


def test_empty_and_oversized_batches(client, db):
    """Empty batch (< 1) and oversized batch (> 50) return 422."""
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Empty
    res_empty = client.post(
        f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json={"actions": []}
    )
    assert res_empty.status_code == 422

    # Oversized (> 50)
    oversized_actions = [
        {
            "task_id": i + 1,
            "action_type": "REASSIGN",
            "new_assignee_id": w["emp2"].emp_id,
            "reason": f"Bulk reassignment reason for action {i}.",
        }
        for i in range(51)
    ]
    res_over = client.post(
        f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks",
        json={"actions": oversized_actions},
    )
    assert res_over.status_code == 422


def test_warning_generation(client, db):
    """
    Warnings are generated when:
    1. Extended deadline falls within the applicant's leave period.
    2. Extended deadline exceeds milestone target date.
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    # Applicant leave period is 2026-12-05 to 2026-12-12
    # Milestone target date is 2026-12-20
    # Task 1: new due date 2026-12-10 (inside leave window)
    # Task 2: new due date 2026-12-25 (exceeds milestone target date)
    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-10",
                "reason": "Extension falling inside applicant leave window.",
            },
            {
                "task_id": w["task2"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-25",
                "reason": "Extension exceeding milestone target date.",
            },
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["reallocated_count"] == 2
    assert len(data["warnings"]) == 2
    assert any("falls within the leave period" in w_msg for w_msg in data["warnings"])
    assert any("exceeds milestone target date" in w_msg for w_msg in data["warnings"])


def test_failure_during_application_phase_rolls_back_entire_batch(client, db, monkeypatch):
    """
    Failure occurring during the database modification / notification phase
    must roll back all task changes, notifications, and audit records.
    """
    w = setup_world(db)
    app.dependency_overrides[get_current_user] = lambda: w["tl1_u"]

    original_apply = app_features_tasks_service_apply_reassign = None
    from app.features.tasks.service import TaskService
    original_apply = TaskService._apply_reassignment

    call_count = [0]

    def faulty_apply(db, task, new_assignee, reason, actor, ip, *, commit=False, extra_audit_data=None):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Simulated transient failure on second task modification")
        return original_apply(
            db, task, new_assignee, reason, actor, ip, commit=commit, extra_audit_data=extra_audit_data
        )

    monkeypatch.setattr(TaskService, "_apply_reassignment", faulty_apply)

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "First valid task reassignment.",
            },
            {
                "task_id": w["task2"].task_id,
                "action_type": "REASSIGN",
                "new_assignee_id": w["emp2"].emp_id,
                "reason": "Second task reassignment triggering failure.",
            },
        ]
    }

    with pytest.raises(RuntimeError, match="Simulated transient failure"):
        client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)

    # Verify task 1 was rolled back completely
    db.refresh(w["task1"])
    assert w["task1"].assigned_to == w["emp1"].emp_id

    # Verify no audit logs persisted
    audits = db.query(AuditLog).filter(AuditLog.entity_name == "TASK").all()
    assert len(audits) == 0

    # Verify no notifications persisted
    notes = db.query(Notification).all()
    assert len(notes) == 0


def test_elevated_pm_grant_without_pm_row_returns_403(client, db):
    """
    Test: Employee with elevated PM grant but no ProjectManager row.
    Even if a project has pm_id == employee.emp_id, resolve_pm returns None,
    and authorize_actor must return 403 Forbidden (not fall back to employee.emp_id).
    """
    w = setup_world(db)
    emp_u = make_user(db, UserType.EMPLOYEE, "elevated_pm@example.com")
    emp = make_employee(db, emp_u, "Elevated PM Employee")

    # Give active elevated PM grant
    grant = ElevatedAccessGrant(
        user_id=emp_u.account_id,
        granted_role="PM",
        reason="Coverage during PM absence",
        granted_by=w["admin_u"].account_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(grant)

    # Set project 1 pm_id to equal emp.emp_id so an incorrect fallback would pass
    w["prj1"].pm_id = emp.emp_id
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: emp_u

    payload = {
        "actions": [
            {
                "task_id": w["task1"].task_id,
                "action_type": "EXTEND_DEADLINE",
                "new_due_date": "2026-12-15",
                "reason": "Elevated employee trying to reallocate PM task.",
            }
        ]
    }

    res = client.post(f"/api/v1/leave/requests/{w['leave_req'].leave_id}/reallocate-tasks", json=payload)
    assert res.status_code == 403
    assert "No PM profile found for current user" in res.json()["detail"]

