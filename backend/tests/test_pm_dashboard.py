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
    CommonStatus,
    MilestoneStatus,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
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
