"""
Tests for Overdue Escalation (S5: US-15 Monitor Overdue Work, US-19 Notifications).

Verifies:
  - Overdue predicate excludes DONE tasks, null due dates and CANCELLED projects
  - days_overdue = today - due_date with a pinned 'today'
  - Team Lead and PM scoping isolation; EMPLOYEE gets 403
  - Sweep notifies TL + assignee once per overdue episode, writes one audit row
  - Changing due_date resets the episode
  - GET /tasks/overdue is not shadowed by GET /tasks/{id}
"""

import json
import uuid
from datetime import date, timedelta
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.tasks.overdue import OverdueService, apply_due_date_change
from app.features.tasks.router import get_today
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team
from app.models.user_account import UserAccount

TODAY = date(2026, 11, 18)


# ------------------------------------------------------------------
# Fixtures & Helpers
# ------------------------------------------------------------------

@pytest.fixture
def test_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_today] = lambda: TODAY
    try:
        yield {"db": db, "client": TestClient(app)}
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def _save(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _user(db, user_type: UserType) -> UserAccount:
    return _save(db, UserAccount(
        account_id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@company.com",
        password_hash="hash",
        user_type=user_type,
        is_active=True,
    ))


def _employee(db, name: str, user_type: UserType = UserType.EMPLOYEE) -> Employee:
    acc = _user(db, user_type)
    return _save(db, Employee(
        account_id=acc.account_id,
        emp_code=f"E_{uuid.uuid4().hex[:6]}",
        full_name=name,
        email=f"emp_{uuid.uuid4().hex[:6]}@company.com",
        designation="Engineer",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    ))


def _pm(db) -> ProjectManager:
    acc = _user(db, UserType.PM)
    return _save(db, ProjectManager(
        account_id=acc.account_id,
        emp_code=f"PM_{uuid.uuid4().hex[:6]}",
        full_name="Project Manager",
        email=f"pm_{uuid.uuid4().hex[:6]}@company.com",
        date_of_joining=date(2024, 1, 1),
        status=CommonStatus.ACTIVE,
    ))


def _project(db, pm: ProjectManager, status: ProjectStatus = ProjectStatus.ACTIVE) -> Project:
    client = _save(db, Client(
        company_name="Acme Corp",
        contact_person="Client Rep",
        email=f"client_{uuid.uuid4().hex[:6]}@acme.com",
        status=CommonStatus.ACTIVE,
    ))
    return _save(db, Project(
        client_id=client.client_id,
        pm_id=pm.pm_id,
        project_code=f"P_{uuid.uuid4().hex[:6]}",
        name=f"Project {uuid.uuid4().hex[:4]}",
        start_date=date(2026, 1, 1),
        status=status,
    ))


def _team(db, project: Project, lead: Optional[Employee]) -> Team:
    return _save(db, Team(
        project_id=project.project_id,
        lead_emp_id=lead.emp_id if lead else None,
        name=f"Team {uuid.uuid4().hex[:4]}",
        status=TeamStatus.ACTIVE,
    ))


def _task(
    db,
    project: Project,
    team: Team,
    due: Optional[date],
    assignee: Optional[Employee] = None,
    status: TaskStatus = TaskStatus.IN_PROGRESS,
    priority: PriorityLevel = PriorityLevel.MEDIUM,
    title: str = "Task",
) -> Task:
    return _save(db, Task(
        project_id=project.project_id,
        team_id=team.team_id,
        assigned_to=assignee.emp_id if assignee else None,
        title=title,
        priority=priority,
        status=status,
        due_date=due,
    ))


def _as(user: UserAccount):
    app.dependency_overrides[get_current_user] = lambda: user


def _account(db, account_id) -> UserAccount:
    return db.get(UserAccount, account_id)


def _admin(db) -> UserAccount:
    return _user(db, UserType.ADMIN)


@pytest.fixture
def world(test_setup):
    """Two PMs, two projects, two teams with different leads."""
    db = test_setup["db"]
    pm_a, pm_b = _pm(db), _pm(db)
    proj_a, proj_b = _project(db, pm_a), _project(db, pm_b)
    lead_a = _employee(db, "Lead A", UserType.TEAM_LEAD)
    lead_b = _employee(db, "Lead B", UserType.TEAM_LEAD)
    team_a, team_b = _team(db, proj_a, lead_a), _team(db, proj_b, lead_b)
    dev = _employee(db, "Sarah Connor")
    return {**test_setup, "pm_a": pm_a, "pm_b": pm_b, "proj_a": proj_a, "proj_b": proj_b,
            "lead_a": lead_a, "lead_b": lead_b, "team_a": team_a, "team_b": team_b, "dev": dev}


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_overdue_detection_excludes_done_null_due_and_cancelled_projects(world):
    db = world["db"]
    proj, team = world["proj_a"], world["team_a"]
    yesterday = TODAY - timedelta(days=1)

    overdue = _task(db, proj, team, yesterday, title="overdue")
    _task(db, proj, team, yesterday, status=TaskStatus.DONE, title="done")
    _task(db, proj, team, None, title="no due date")
    _task(db, proj, team, TODAY, title="due today")
    _task(db, proj, team, TODAY + timedelta(days=3), title="future")
    for st in (TaskStatus.TODO, TaskStatus.IN_REVIEW, TaskStatus.BLOCKED, TaskStatus.REJECTED):
        _task(db, proj, team, yesterday, status=st, title=f"open-{st.value}")

    cancelled = _project(db, world["pm_a"], status=ProjectStatus.CANCELLED)
    _task(db, cancelled, _team(db, cancelled, world["lead_a"]), yesterday, title="cancelled project")

    ids = {t.task_id for t in db.scalars(OverdueService.base_query(db, TODAY))}
    titles = {db.get(Task, i).title for i in ids}
    assert overdue.task_id in ids
    assert titles == {"overdue", "open-TODO", "open-IN_REVIEW", "open-BLOCKED", "open-REJECTED"}


def test_days_overdue_calculation_accuracy(world):
    db, client = world["db"], world["client"]
    proj, team, dev = world["proj_a"], world["team_a"], world["dev"]
    milestone = _save(db, ProjectMilestone(
        project_id=proj.project_id, title="Sprint 2 Deliverables", target_date=TODAY,
    ))
    t5 = _task(db, proj, team, TODAY - timedelta(days=5), assignee=dev,
               priority=PriorityLevel.CRITICAL, title="Database Index Optimization")
    t5.milestone_id = milestone.id
    db.commit()
    _task(db, proj, team, TODAY - timedelta(days=1), priority=PriorityLevel.LOW, title="one day")
    _task(db, proj, team, TODAY - timedelta(days=5), priority=PriorityLevel.LOW, title="five low")
    _task(db, proj, team, TODAY - timedelta(days=30), priority=PriorityLevel.MEDIUM, title="thirty")

    _as(_admin(db))
    res = client.get("/api/v1/tasks/overdue")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_overdue"] == 4
    # days_overdue DESC, then CRITICAL before LOW on ties.
    assert [(i["title"], i["days_overdue"]) for i in body["items"]] == [
        ("thirty", 30), ("Database Index Optimization", 5), ("five low", 5), ("one day", 1),
    ]
    row = body["items"][1]
    assert row["due_date"] == (TODAY - timedelta(days=5)).isoformat()
    assert row["project_name"] == proj.name
    assert row["team_lead_name"] == "Lead A"
    assert row["assignee_id"] == dev.emp_id
    assert row["assignee_name"] == "Sarah Connor"
    assert row["milestone_title"] == "Sprint 2 Deliverables"
    assert row["priority"] == "CRITICAL"
    assert row["status"] == "IN_PROGRESS"

    # Pagination and filters.
    page2 = client.get("/api/v1/tasks/overdue", params={"page": 2, "limit": 3}).json()
    assert page2["total_overdue"] == 4 and [i["title"] for i in page2["items"]] == ["one day"]
    crit = client.get("/api/v1/tasks/overdue", params={"priority": "CRITICAL"}).json()
    assert [i["task_id"] for i in crit["items"]] == [t5.task_id]
    mine = client.get("/api/v1/tasks/overdue", params={"assignee_id": dev.emp_id}).json()
    assert mine["total_overdue"] == 1


def test_team_lead_scoping_isolation(world):
    db, client = world["db"], world["client"]
    past = TODAY - timedelta(days=2)
    a = _task(db, world["proj_a"], world["team_a"], past)
    _task(db, world["proj_b"], world["team_b"], past)

    _as(_account(db, world["lead_a"].account_id))
    body = client.get("/api/v1/tasks/overdue").json()
    assert [i["task_id"] for i in body["items"]] == [a.task_id]
    assert all(i["days_overdue"] > 0 for i in body["items"])
    # Filtering to another team cannot widen scope.
    other = client.get("/api/v1/tasks/overdue", params={"team_id": world["team_b"].team_id}).json()
    assert other["total_overdue"] == 0

    # A TL with no led teams sees nothing; an EMPLOYEE is rejected.
    _as(_account(db, _employee(db, "Lonely Lead", UserType.TEAM_LEAD).account_id))
    assert client.get("/api/v1/tasks/overdue").json()["total_overdue"] == 0
    _as(_account(db, world["dev"].account_id))
    assert client.get("/api/v1/tasks/overdue").status_code == 403


def test_pm_scoping_isolation(world):
    db, client = world["db"], world["client"]
    past = TODAY - timedelta(days=2)
    a1 = _task(db, world["proj_a"], world["team_a"], past)
    second_team = _team(db, world["proj_a"], world["lead_b"])
    a2 = _task(db, world["proj_a"], second_team, past)
    _task(db, world["proj_b"], world["team_b"], past)

    _as(_account(db, world["pm_a"].account_id))
    body = client.get("/api/v1/tasks/overdue").json()
    assert {i["task_id"] for i in body["items"]} == {a1.task_id, a2.task_id}
    assert body["total_overdue"] == 2

    other = client.get("/api/v1/tasks/overdue", params={"project_id": world["proj_b"].project_id}).json()
    assert other["total_overdue"] == 0


def test_overdue_sweep_emits_notifications_idempotently(world):
    db, client = world["db"], world["client"]
    lead, dev = world["lead_a"], world["dev"]
    past = TODAY - timedelta(days=3)
    task = _task(db, world["proj_a"], world["team_a"], past, assignee=dev)
    _task(db, world["proj_a"], world["team_a"], past)  # unassigned: TL only
    _task(db, world["proj_a"], world["team_a"], TODAY + timedelta(days=1), assignee=dev)  # not overdue

    # Only ADMIN / SYSTEM_ADMIN may sweep.
    _as(_account(db, world["pm_a"].account_id))
    assert client.post("/api/v1/tasks/check-overdue").status_code == 403

    _as(_user(db, UserType.SYSTEM_ADMIN))
    first = client.post("/api/v1/tasks/check-overdue")
    assert first.status_code == 200, first.text
    assert first.json() == {"evaluated_tasks": 2, "newly_flagged_overdue": 2, "already_flagged": 0}

    lead_notes = db.query(Notification).filter_by(account_id=lead.account_id).all()
    dev_notes = db.query(Notification).filter_by(account_id=dev.account_id).all()
    assert sorted(n.type for n in lead_notes) == ["TASK_OVERDUE", "TASK_OVERDUE"]
    assert [n.type for n in dev_notes] == ["TASK_DEADLINE_MISSED"]
    assert dev_notes[0].link == f"/tasks/{task.task_id}"
    db.refresh(task)
    assert task.overdue_notified_at is not None

    audits = db.query(AuditLog).filter_by(entity_name="TASK_OVERDUE_SWEEP").all()
    assert len(audits) == 1 and audits[0].entity_ref_id == "sweep"
    assert json.loads(audits[0].new_value)["newly_flagged_overdue"] == 2

    # Second run with no changes: nothing new.
    second = client.post("/api/v1/tasks/check-overdue").json()
    assert second == {"evaluated_tasks": 2, "newly_flagged_overdue": 0, "already_flagged": 2}
    assert db.query(Notification).count() == 3
    assert db.query(AuditLog).filter_by(entity_name="TASK_OVERDUE_SWEEP").count() == 2

    # Moving the due date opens a new episode; the next sweep notifies again.
    apply_due_date_change(task, TODAY - timedelta(days=1))
    db.commit()
    assert task.overdue_notified_at is None
    third = client.post("/api/v1/tasks/check-overdue").json()
    assert third == {"evaluated_tasks": 2, "newly_flagged_overdue": 1, "already_flagged": 1}
    assert db.query(Notification).count() == 5


def test_apply_due_date_change_keeps_flag_when_date_unchanged(world):
    db = world["db"]
    task = _task(db, world["proj_a"], world["team_a"], TODAY - timedelta(days=2))
    OverdueService.run_sweep(db, _admin(db), TODAY)
    db.refresh(task)
    flagged_at = task.overdue_notified_at
    apply_due_date_change(task, task.due_date)
    assert task.overdue_notified_at == flagged_at


def test_overdue_route_not_shadowed_by_task_id_route(world):
    client = world["client"]
    _as(_admin(world["db"]))
    res = client.get("/api/v1/tasks/overdue")
    assert res.status_code == 200, res.text
    assert res.json() == {"total_overdue": 0, "page": 1, "limit": 20, "items": []}
