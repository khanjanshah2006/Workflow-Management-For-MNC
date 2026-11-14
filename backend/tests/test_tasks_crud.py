import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401 — ensure all models are registered on Base.metadata
from app.features.tasks.router import (
    create_task,
    get_my_tasks,
    get_project_tasks,
    get_task_detail,
)
from app.features.tasks.schemas import TaskCreate
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.project_manager import ProjectManager
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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_data(db_session):
    """Seed PM, Team Lead, two Employees, Client, Project, Team, and Milestone."""
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@example.com",
        password_hash="fakehash",
        user_type=UserType.PM,
        is_active=True,
    )
    lead_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="lead@example.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    dev_a_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="deva@example.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    dev_b_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="devb@example.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([pm_acc, lead_acc, dev_a_acc, dev_b_acc])
    db_session.flush()

    pm_emp = Employee(
        account_id=pm_acc.account_id,
        emp_code="EMP-PM",
        full_name="Priya PM",
        email="pm@example.com",
        designation="Project Manager",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    lead_emp = Employee(
        account_id=lead_acc.account_id,
        emp_code="EMP-LEAD",
        full_name="Leo Lead",
        email="lead@example.com",
        designation="Tech Lead",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    dev_a_emp = Employee(
        account_id=dev_a_acc.account_id,
        emp_code="EMP-DEVA",
        full_name="Alice Dev",
        email="deva@example.com",
        designation="Software Engineer",
        date_of_joining=date(2025, 2, 1),
        status=CommonStatus.ACTIVE,
    )
    dev_b_emp = Employee(
        account_id=dev_b_acc.account_id,
        emp_code="EMP-DEVB",
        full_name="Bob Outsider",
        email="devb@example.com",
        designation="Software Engineer",
        date_of_joining=date(2025, 2, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([pm_emp, lead_emp, dev_a_emp, dev_b_emp])
    db_session.flush()

    client = Client(
        company_name="Acme Corp",
        contact_person="Jane Doe",
        email="client@acme.com",
        status=CommonStatus.ACTIVE,
    )
    pm_profile = ProjectManager(
        account_id=pm_acc.account_id,
        emp_code="EMP-PM",
        full_name="Priya PM",
        email="pm@example.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([client, pm_profile])
    db_session.flush()

    project = Project(
        client_id=client.client_id,
        pm_id=pm_profile.pm_id,
        project_code="PRJ-001",
        name="WMS Core Platform",
        start_date=date(2026, 11, 1),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(project)
    db_session.flush()

    team = Team(
        project_id=project.project_id,
        lead_emp_id=lead_emp.emp_id,
        name="Backend Core Team",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.flush()

    # Only lead_emp and dev_a_emp are on the team (dev_b_emp is NOT)
    db_session.add_all([
        TeamMember(team_id=team.team_id, emp_id=lead_emp.emp_id),
        TeamMember(team_id=team.team_id, emp_id=dev_a_emp.emp_id),
    ])

    milestone = ProjectMilestone(
        project_id=project.project_id,
        title="Wave 2 Backend",
        target_date=date(2026, 11, 30),
    )
    db_session.add(milestone)
    db_session.commit()

    return {
        "pm_acc": pm_acc,
        "lead_acc": lead_acc,
        "dev_a_acc": dev_a_acc,
        "dev_b_acc": dev_b_acc,
        "pm_emp": pm_emp,
        "lead_emp": lead_emp,
        "dev_a_emp": dev_a_emp,
        "dev_b_emp": dev_b_emp,
        "project": project,
        "team": team,
        "milestone": milestone,
    }


def _fake_request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def test_create_task_success_by_pm(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        milestone_id=seed_data["milestone"].id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Implement JWT Refresh Token Flow",
        description="Store refresh tokens with rotation and 7-day TTL.",
        priority=PriorityLevel.HIGH,
        start_date=date(2026, 11, 10),
        due_date=date(2026, 11, 15),
    )
    task = create_task(
        payload=payload,
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    assert task.task_id is not None
    assert task.status == TaskStatus.TODO
    assert task.progress_pct == 0
    assert task.rejection_count == 0
    assert task.created_by == seed_data["pm_emp"].emp_id
    assert task.assigned_to == seed_data["dev_a_emp"].emp_id


def test_create_task_success_by_team_lead(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Setup Redis Cache",
        priority=PriorityLevel.MEDIUM,
    )
    task = create_task(
        payload=payload,
        request=_fake_request(),
        current_user=seed_data["lead_acc"],
        db=db_session,
    )
    assert task.status == TaskStatus.TODO
    assert task.created_by == seed_data["lead_emp"].emp_id


def test_create_task_forbidden_for_regular_employee(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Unauthorized Task",
    )
    with pytest.raises(HTTPException) as exc:
        create_task(
            payload=payload,
            request=_fake_request(),
            current_user=seed_data["dev_a_acc"],
            db=db_session,
        )
    assert exc.value.status_code == 403


def test_create_task_assignee_not_on_team(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        assigned_to=seed_data["dev_b_emp"].emp_id,  # NOT in team
        title="Invalid Assignee Task",
    )
    with pytest.raises(HTTPException) as exc:
        create_task(
            payload=payload,
            request=_fake_request(),
            current_user=seed_data["pm_acc"],
            db=db_session,
        )
    assert exc.value.status_code == 400


def test_create_task_invalid_dates(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Invalid Dates Task",
        start_date=date(2026, 11, 20),
        due_date=date(2026, 11, 10),
    )
    with pytest.raises(HTTPException) as exc:
        create_task(
            payload=payload,
            request=_fake_request(),
            current_user=seed_data["pm_acc"],
            db=db_session,
        )
    assert exc.value.status_code == 400


def test_create_task_not_found_entities(db_session, seed_data):
    # Missing project
    with pytest.raises(HTTPException) as exc_proj:
        create_task(
            payload=TaskCreate(
                project_id=9999,
                team_id=seed_data["team"].team_id,
                title="Missing Project",
            ),
            request=_fake_request(),
            current_user=seed_data["pm_acc"],
            db=db_session,
        )
    assert exc_proj.value.status_code == 404

    # Missing team
    with pytest.raises(HTTPException) as exc_team:
        create_task(
            payload=TaskCreate(
                project_id=seed_data["project"].project_id,
                team_id=9999,
                title="Missing Team",
            ),
            request=_fake_request(),
            current_user=seed_data["pm_acc"],
            db=db_session,
        )
    assert exc_team.value.status_code == 404

    # Missing milestone
    with pytest.raises(HTTPException) as exc_ms:
        create_task(
            payload=TaskCreate(
                project_id=seed_data["project"].project_id,
                team_id=seed_data["team"].team_id,
                milestone_id=9999,
                title="Missing Milestone",
            ),
            request=_fake_request(),
            current_user=seed_data["pm_acc"],
            db=db_session,
        )
    assert exc_ms.value.status_code == 404


def test_create_task_audit_logged(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Audit Logged Task",
    )
    task = create_task(
        payload=payload,
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_name == "TASK",
            AuditLog.entity_ref_id == str(task.task_id),
        )
        .first()
    )
    assert log is not None
    assert log.action == AuditAction.CREATE
    assert log.account_id == seed_data["pm_acc"].account_id


def test_get_task_detail_and_not_found(db_session, seed_data):
    payload = TaskCreate(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        milestone_id=seed_data["milestone"].id,
        assigned_to=seed_data["dev_a_emp"].emp_id,
        title="Detailed Task",
    )
    created = create_task(
        payload=payload,
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    detail = get_task_detail(
        id=created.task_id,
        current_user=seed_data["dev_a_acc"],
        db=db_session,
    )
    assert detail.project.name == "WMS Core Platform"
    assert detail.milestone.title == "Wave 2 Backend"
    assert detail.assignee.full_name == "Alice Dev"
    assert detail.creator.full_name == "Priya PM"

    with pytest.raises(HTTPException) as exc:
        get_task_detail(id=9999, current_user=seed_data["dev_a_acc"], db=db_session)
    assert exc.value.status_code == 404


def test_my_tasks_scoped_and_filtered(db_session, seed_data):
    # Create 2 tasks for dev_a, 1 task for lead
    create_task(
        payload=TaskCreate(
            project_id=seed_data["project"].project_id,
            team_id=seed_data["team"].team_id,
            assigned_to=seed_data["dev_a_emp"].emp_id,
            title="Dev A High Task",
            priority=PriorityLevel.HIGH,
        ),
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    create_task(
        payload=TaskCreate(
            project_id=seed_data["project"].project_id,
            team_id=seed_data["team"].team_id,
            assigned_to=seed_data["dev_a_emp"].emp_id,
            title="Dev A Low Task",
            priority=PriorityLevel.LOW,
        ),
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    create_task(
        payload=TaskCreate(
            project_id=seed_data["project"].project_id,
            team_id=seed_data["team"].team_id,
            assigned_to=seed_data["lead_emp"].emp_id,
            title="Lead Task",
            priority=PriorityLevel.HIGH,
        ),
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )

    all_dev_a = get_my_tasks(
        status_filter=None,
        priority=None,
        page=1,
        limit=20,
        current_user=seed_data["dev_a_acc"],
        db=db_session,
    )
    assert all_dev_a.total == 2
    assert all(t.assigned_to == seed_data["dev_a_emp"].emp_id for t in all_dev_a.items)

    high_dev_a = get_my_tasks(
        status_filter=TaskStatus.TODO,
        priority=PriorityLevel.HIGH,
        page=1,
        limit=20,
        current_user=seed_data["dev_a_acc"],
        db=db_session,
    )
    assert high_dev_a.total == 1
    assert high_dev_a.items[0].title == "Dev A High Task"


def test_project_tasks_list_and_filters(db_session, seed_data):
    create_task(
        payload=TaskCreate(
            project_id=seed_data["project"].project_id,
            team_id=seed_data["team"].team_id,
            milestone_id=seed_data["milestone"].id,
            assigned_to=seed_data["dev_a_emp"].emp_id,
            title="Milestone Task",
        ),
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    create_task(
        payload=TaskCreate(
            project_id=seed_data["project"].project_id,
            team_id=seed_data["team"].team_id,
            milestone_id=None,
            assigned_to=seed_data["dev_a_emp"].emp_id,
            title="Backlog Task",
        ),
        request=_fake_request(),
        current_user=seed_data["pm_acc"],
        db=db_session,
    )

    res_all = get_project_tasks(
        project_id=seed_data["project"].project_id,
        team_id=None,
        milestone_id=None,
        status_filter=None,
        page=1,
        limit=20,
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    assert res_all.total == 2

    res_ms = get_project_tasks(
        project_id=seed_data["project"].project_id,
        team_id=seed_data["team"].team_id,
        milestone_id=seed_data["milestone"].id,
        status_filter=TaskStatus.TODO,
        page=1,
        limit=20,
        current_user=seed_data["pm_acc"],
        db=db_session,
    )
    assert res_ms.total == 1
    assert res_ms.items[0].title == "Milestone Task"
