"""
Tests for the PM Risk & Quality Dashboard (S5-BE-2: US-23, US-38, US-39).

Covers project access (404 -> 403), dashboard aggregates, repeated rejections with
audit-log history, the risk score formula, blocked tasks and cross-project team workload.
"""

import uuid
from datetime import date, timedelta
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.audit import write_audit_log
from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.features.projects.risk_service import ProjectRiskService
from app.features.projects.service import ProjectNotFoundError, UnauthorizedProjectAccessError
from app.features.tasks.router import get_today
from app.main import app
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    MilestoneStatus,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.system_parameter import SystemParameter
from app.models.task import Task
from app.models.team import Team
from app.models.user_account import UserAccount

TODAY = date(2026, 11, 18)


# ------------------------------------------------------------------
# Fixtures & Helpers
# ------------------------------------------------------------------

@pytest.fixture
def setup():
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


def _employee(db, name: str) -> Employee:
    acc = _user(db, UserType.EMPLOYEE)
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


def _pm_account(db, pm: ProjectManager) -> UserAccount:
    return db.get(UserAccount, pm.account_id)


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
        name="Alpha ERP Modernization",
        start_date=date(2026, 1, 1),
        status=status,
    ))


def _team(db, project: Project) -> Team:
    return _save(db, Team(
        project_id=project.project_id,
        name=f"Team {uuid.uuid4().hex[:4]}",
        status=TeamStatus.ACTIVE,
    ))


def _task(
    db,
    project: Project,
    team: Team,
    status: TaskStatus = TaskStatus.IN_PROGRESS,
    due: Optional[date] = None,
    assignee: Optional[Employee] = None,
    milestone: Optional[ProjectMilestone] = None,
    rejection_count: int = 0,
    title: str = "Task",
    blocker_reason: Optional[str] = None,
) -> Task:
    return _save(db, Task(
        project_id=project.project_id,
        team_id=team.team_id,
        milestone_id=milestone.id if milestone else None,
        assigned_to=assignee.emp_id if assignee else None,
        title=title,
        status=status,
        due_date=due,
        rejection_count=rejection_count,
        blocker_reason=blocker_reason,
    ))


def _milestone(
    db,
    project: Project,
    target: date,
    status: MilestoneStatus = MilestoneStatus.PENDING,
    is_deleted: bool = False,
    title: str = "Milestone",
) -> ProjectMilestone:
    return _save(db, ProjectMilestone(
        project_id=project.project_id,
        title=title,
        target_date=target,
        status=status,
        is_deleted=is_deleted,
    ))


def _as(user: UserAccount):
    app.dependency_overrides[get_current_user] = lambda: user


# ------------------------------------------------------------------
# Access (404 -> 403)
# ------------------------------------------------------------------

def test_unassigned_pm_forbidden_403(setup):
    db = setup["db"]
    owner, other = _pm(db), _pm(db)
    project = _project(db, owner)

    with pytest.raises(UnauthorizedProjectAccessError):
        ProjectRiskService.get_authorized_project(db, project.project_id, _pm_account(db, other))
    with pytest.raises(ProjectNotFoundError):
        ProjectRiskService.get_authorized_project(db, 9999, _pm_account(db, other))

    assert ProjectRiskService.get_authorized_project(db, project.project_id, _pm_account(db, owner)) is not None
    for role in (UserType.ADMIN, UserType.SYSTEM_ADMIN):
        assert ProjectRiskService.get_authorized_project(db, project.project_id, _user(db, role)) is not None


# ------------------------------------------------------------------
# Aggregate helpers
# ------------------------------------------------------------------

def test_status_counts_include_every_status(setup):
    db = setup["db"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    for status in (TaskStatus.DONE, TaskStatus.DONE, TaskStatus.REJECTED, TaskStatus.TODO):
        _task(db, project, team, status=status)

    counts = ProjectRiskService.status_counts(db, project.project_id)

    assert set(counts) == {s.value for s in TaskStatus}
    assert counts["DONE"] == 2 and counts["REJECTED"] == 1 and counts["TODO"] == 1
    assert counts["IN_REVIEW"] == 0


def test_milestone_windows_and_overdue_milestones(setup):
    db = setup["db"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    soon = _milestone(db, project, TODAY + timedelta(days=3), title="Due in 3 days")
    soon_done = _milestone(db, project, TODAY + timedelta(days=1), title="Only DONE tasks")
    _milestone(db, project, TODAY + timedelta(days=10), title="Upcoming")
    _milestone(db, project, TODAY - timedelta(days=1), title="Overdue")
    _milestone(db, project, TODAY - timedelta(days=5), status=MilestoneStatus.COMPLETED)
    _milestone(db, project, TODAY + timedelta(days=2), is_deleted=True)
    _task(db, project, team, milestone=soon)
    _task(db, project, team, milestone=soon_done, status=TaskStatus.DONE)

    at_risk = ProjectRiskService.at_risk_milestones(db, project.project_id, TODAY)
    upcoming = ProjectRiskService.milestones_due_between(
        db, project.project_id, TODAY, TODAY + timedelta(days=14)
    )

    assert [m["title"] for m in at_risk] == ["Due in 3 days"]
    assert at_risk[0]["open_tasks"] == 1
    assert [m["title"] for m in upcoming] == ["Only DONE tasks", "Due in 3 days", "Upcoming"]
    assert ProjectRiskService.overdue_milestones_count(db, project.project_id, TODAY) == 1


def test_overdue_and_repeated_rejection_counts(setup):
    db = setup["db"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    _task(db, project, team, due=TODAY - timedelta(days=2))
    _task(db, project, team, due=TODAY - timedelta(days=2), status=TaskStatus.DONE)
    _task(db, project, team, due=TODAY)
    _task(db, project, team, rejection_count=2, status=TaskStatus.REJECTED)
    _task(db, project, team, rejection_count=5, status=TaskStatus.DONE)
    _task(db, project, team, rejection_count=1, status=TaskStatus.REJECTED)

    assert ProjectRiskService.overdue_tasks_count(db, project.project_id, TODAY) == 1
    assert ProjectRiskService.repeatedly_rejected_count(db, project.project_id, threshold=2) == 1
    assert ProjectRiskService.repeatedly_rejected_count(db, project.project_id, threshold=1) == 2


# ------------------------------------------------------------------
# GET /api/v1/projects/{id}/dashboard
# ------------------------------------------------------------------

def test_pm_dashboard_aggregates_accurate_status_counts(setup):
    db, client = setup["db"], setup["client"]
    pm = _pm(db)
    project = _project(db, pm)
    team = _team(db, project)
    milestone = _milestone(db, project, TODAY + timedelta(days=2), title="Sprint 2")
    statuses = [TaskStatus.DONE] * 3 + [TaskStatus.TODO, TaskStatus.BLOCKED, TaskStatus.REJECTED, TaskStatus.IN_REVIEW]
    for status in statuses:
        _task(db, project, team, status=status, milestone=milestone)
    _task(db, project, team, status=TaskStatus.IN_PROGRESS, due=TODAY - timedelta(days=1), rejection_count=2)

    _as(_pm_account(db, pm))
    res = client.get(f"/api/v1/projects/{project.project_id}/dashboard")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_tasks"] == 8
    assert body["tasks_by_status"] == {
        "TODO": 1, "IN_PROGRESS": 1, "IN_REVIEW": 1, "DONE": 3, "BLOCKED": 1, "REJECTED": 1,
    }
    assert body["completion_pct"] == round(3 / 8 * 100)
    assert body["overdue_tasks_count"] == 1
    assert body["blocked_tasks_count"] == 1
    assert body["at_risk_milestones_count"] == 1
    assert body["repeatedly_rejected_count"] == 1
    assert body["rejection_threshold"] == 2
    assert body["upcoming_milestones"] == [{
        "milestone_id": milestone.id, "title": "Sprint 2",
        "target_date": (TODAY + timedelta(days=2)).isoformat(), "open_tasks": 4,
    }]


def test_dashboard_empty_project_has_zero_completion(setup):
    db, client = setup["db"], setup["client"]
    project = _project(db, _pm(db))

    _as(_user(db, UserType.ADMIN))
    body = client.get(f"/api/v1/projects/{project.project_id}/dashboard").json()

    assert body["total_tasks"] == 0 and body["completion_pct"] == 0
    assert all(v == 0 for v in body["tasks_by_status"].values())


def test_dashboard_access_codes(setup):
    db, client = setup["db"], setup["client"]
    project = _project(db, _pm(db))

    _as(_pm_account(db, _pm(db)))
    assert client.get(f"/api/v1/projects/{project.project_id}/dashboard").status_code == 403
    assert client.get("/api/v1/projects/9999/dashboard").status_code == 404

    _as(_user(db, UserType.EMPLOYEE))
    assert client.get(f"/api/v1/projects/{project.project_id}/dashboard").status_code == 403

    _as(_user(db, UserType.SYSTEM_ADMIN))
    assert client.get(f"/api/v1/projects/{project.project_id}/dashboard").status_code == 200


# ------------------------------------------------------------------
# Repeated rejections & audit-log history
# ------------------------------------------------------------------

def _reject(db, task: Task, feedback: str, count: int):
    """Write the audit row TaskService.review_task writes on rejection."""
    write_audit_log(
        db=db, action=AuditAction.UPDATE, entity_name="TASK", entity_ref_id=str(task.task_id),
        old_value={"status": "IN_REVIEW"},
        new_value={"status": "REJECTED", "rejection_feedback": feedback, "rejection_count": count},
    )


def test_rejection_history_built_from_audit_log(setup):
    db = setup["db"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    kyle = _employee(db, "Kyle Reese")
    task = _task(db, project, team, status=TaskStatus.REJECTED, rejection_count=3,
                 assignee=kyle, title="OAuth2 Callback Handler")
    other = _task(db, project, team, status=TaskStatus.REJECTED, rejection_count=2)
    feedback = ["Missing error handling.", "Edge cases untested.", "Unit tests failing in CI pipeline."]
    for i, text in enumerate(feedback, start=1):
        _reject(db, task, text, i)
    # Noise: an approval on the same task and a rejection on another task.
    write_audit_log(db=db, action=AuditAction.UPDATE, entity_name="TASK",
                    entity_ref_id=str(task.task_id), new_value={"status": "DONE"})
    _reject(db, other, "Other task feedback.", 1)
    task.rejection_feedback = feedback[-1]
    db.commit()

    items = ProjectRiskService.repeatedly_rejected_tasks(db, project.project_id, threshold=3)

    assert len(items) == 1
    item = items[0]
    assert item["task_id"] == task.task_id and item["assignee_name"] == "Kyle Reese"
    assert item["latest_rejection_feedback"] == feedback[-1]
    assert [h["feedback"] for h in item["rejection_history"]] == feedback
    assert all(h["rejected_at"] is not None for h in item["rejection_history"])


def test_repeated_rejections_filter_by_threshold_assignee_and_done(setup):
    db = setup["db"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    sarah, kyle = _employee(db, "Sarah"), _employee(db, "Kyle")
    _task(db, project, team, rejection_count=2, assignee=sarah, title="sarah-2")
    _task(db, project, team, rejection_count=4, assignee=kyle, title="kyle-4")
    _task(db, project, team, rejection_count=1, assignee=kyle, title="kyle-1")
    _task(db, project, team, rejection_count=3, assignee=kyle, status=TaskStatus.DONE, title="kyle-done")

    def titles(**kw):
        return [t["title"] for t in ProjectRiskService.repeatedly_rejected_tasks(db, project.project_id, **kw)]

    assert titles(threshold=2) == ["kyle-4", "sarah-2"]
    assert titles(threshold=3) == ["kyle-4"]
    assert titles(threshold=2, assignee_id=sarah.emp_id) == ["sarah-2"]
    assert titles(threshold=2, include_done=True) == ["kyle-4", "kyle-done", "sarah-2"]


def test_rejection_threshold_reads_system_parameter(setup):
    db = setup["db"]
    assert ProjectRiskService.rejection_threshold(db) == 2
    db.add(SystemParameter(key="REPEATED_REJECTION_THRESHOLD", value="4", value_type="integer"))
    db.commit()
    assert ProjectRiskService.rejection_threshold(db) == 4


# ------------------------------------------------------------------
# Risk score & GET /api/v1/projects/{id}/risks
# ------------------------------------------------------------------

def test_risk_score_formula_boundaries():
    points = ProjectRiskService.risk_points
    level = ProjectRiskService.risk_level
    assert points(overdue=1, blocked=1, repeatedly_rejected=1, milestones_at_risk_or_overdue=1) == 8
    assert points(overdue=0, blocked=0, repeatedly_rejected=0, milestones_at_risk_or_overdue=0) == 0
    assert [level(p) for p in (0, 3, 4, 9, 10, 25)] == ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH"]


def test_risks_filters_by_configurable_threshold(setup):
    db, client = setup["db"], setup["client"]
    pm = _pm(db)
    project = _project(db, pm)
    team = _team(db, project)
    kyle, sarah = _employee(db, "Kyle Reese"), _employee(db, "Sarah Connor")
    flagged = _task(db, project, team, status=TaskStatus.REJECTED, rejection_count=3, assignee=kyle)
    _task(db, project, team, status=TaskStatus.REJECTED, rejection_count=2, assignee=sarah)
    _reject(db, flagged, "Unit tests failing in CI pipeline.", 3)
    _as(_pm_account(db, pm))
    url = f"/api/v1/projects/{project.project_id}/risks"

    body = client.get(url).json()
    assert body["rejection_threshold"] == 2
    assert len(body["repeatedly_rejected_tasks"]) == 2

    db.add(SystemParameter(key="REPEATED_REJECTION_THRESHOLD", value="3", value_type="integer"))
    db.commit()
    body = client.get(url).json()
    assert body["rejection_threshold"] == 3
    assert [t["task_id"] for t in body["repeatedly_rejected_tasks"]] == [flagged.task_id]
    assert body["repeatedly_rejected_tasks"][0]["rejection_history"][0]["feedback"] == "Unit tests failing in CI pipeline."

    body = client.get(url, params={"assignee_id": sarah.emp_id}).json()
    assert body["repeatedly_rejected_tasks"] == []


def test_blocked_tasks_include_blocker_reason(setup):
    db, client = setup["db"], setup["client"]
    pm = _pm(db)
    project = _project(db, pm)
    team = _team(db, project)
    sarah = _employee(db, "Sarah Connor")
    _task(db, project, team, status=TaskStatus.BLOCKED, assignee=sarah, title="Stripe Gateway Integration",
          blocker_reason="Waiting for client merchant test credentials.")
    _task(db, project, team, status=TaskStatus.IN_PROGRESS)

    _as(_pm_account(db, pm))
    body = client.get(f"/api/v1/projects/{project.project_id}/risks").json()

    assert len(body["blocked_tasks"]) == 1
    blocked = body["blocked_tasks"][0]
    assert blocked["title"] == "Stripe Gateway Integration"
    assert blocked["assignee_name"] == "Sarah Connor"
    assert blocked["blocker_reason"] == "Waiting for client merchant test credentials."
    assert blocked["blocked_since"]


def test_risks_score_is_project_wide(setup):
    db, client = setup["db"], setup["client"]
    project = _project(db, _pm(db))
    team = _team(db, project)
    m = _milestone(db, project, TODAY + timedelta(days=1))
    _task(db, project, team, due=TODAY - timedelta(days=3), milestone=m)  # overdue (2) + at-risk milestone (3)
    _task(db, project, team, status=TaskStatus.BLOCKED)                  # blocked (2)
    _task(db, project, team, status=TaskStatus.REJECTED, rejection_count=2)  # repeated rejection (1)
    _milestone(db, project, TODAY - timedelta(days=2))                   # overdue milestone (3)

    _as(_user(db, UserType.SYSTEM_ADMIN))
    body = client.get(f"/api/v1/projects/{project.project_id}/risks").json()

    assert body["risk_points"] == 11
    assert body["risk_score"] == "HIGH"
    assert len(body["at_risk_milestones"]) == 1

    other = _pm(db)
    _as(db.get(UserAccount, other.account_id))
    assert client.get(f"/api/v1/projects/{project.project_id}/risks").status_code == 403


# ------------------------------------------------------------------
# GET /api/v1/projects/{id}/team-workload (US-39)
# ------------------------------------------------------------------

def _assign(db, project: Project, emp: Employee, role: str, released: Optional[date] = None):
    return _save(db, ProjectAssignment(
        project_id=project.project_id, emp_id=emp.emp_id, role_in_project=role,
        assigned_on=date(2026, 1, 1), released_on=released,
    ))


def test_team_workload_aggregates_across_projects_without_detail_leak(setup):
    db, client = setup["db"], setup["client"]
    pm = _pm(db)
    project = _project(db, pm)
    other_project = _project(db, _pm(db))
    team, other_team = _team(db, project), _team(db, other_project)
    matrix, sarah, released = _employee(db, "John Matrix"), _employee(db, "Sarah Connor"), _employee(db, "Gone")
    _assign(db, project, matrix, "Backend Dev")
    _assign(db, other_project, matrix, "Reviewer")
    _assign(db, project, sarah, "QA")
    _assign(db, project, released, "Consultant", released=date(2026, 2, 1))
    _task(db, project, team, assignee=matrix)
    _task(db, project, team, assignee=matrix, status=TaskStatus.REJECTED)
    _task(db, project, team, assignee=matrix, status=TaskStatus.DONE)
    _task(db, other_project, other_team, assignee=matrix, title="Secret other-project task")

    _as(_pm_account(db, pm))
    res = client.get(f"/api/v1/projects/{project.project_id}/team-workload")

    assert res.status_code == 200, res.text
    rows = {r["full_name"]: r for r in res.json()}
    assert set(rows) == {"John Matrix", "Sarah Connor"}
    assert rows["John Matrix"] == {
        "emp_id": matrix.emp_id, "full_name": "John Matrix", "role_in_project": "Backend Dev",
        "open_tasks_in_project": 2, "open_tasks_all_projects": 3,
        "active_projects_count": 2, "utilization_pct": 50.0,
    }
    assert rows["Sarah Connor"]["open_tasks_in_project"] == 0
    assert "Secret other-project task" not in res.text


def test_team_workload_access_codes(setup):
    db, client = setup["db"], setup["client"]
    project = _project(db, _pm(db))

    _as(_pm_account(db, _pm(db)))
    assert client.get(f"/api/v1/projects/{project.project_id}/team-workload").status_code == 403
    assert client.get("/api/v1/projects/9999/team-workload").status_code == 404

    _as(_user(db, UserType.ADMIN))
    res = client.get(f"/api/v1/projects/{project.project_id}/team-workload")
    assert res.status_code == 200 and res.json() == []
