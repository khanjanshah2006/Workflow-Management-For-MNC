import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.employee import Employee
from app.models.enums import AuditAction, UserType
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


APP_DIR = Path(__file__).resolve().parents[1] / "app"
INVALID_ROLE = re.compile(r"\b(HR_MANAGER|PROJECT_MANAGER)\b")


# ==============================================================================
# Shared fixtures: one in-memory SQLite DB for the module, wired into app.main
# ==============================================================================

@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield factory
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    engine.dispose()


@pytest.fixture(scope="module")
def client(session_factory):
    return TestClient(app)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# Seed helpers (unique emails/codes so tests can share the module DB)
# ==============================================================================

def make_account(db, user_type: UserType) -> UserAccount:
    account = UserAccount(
        account_id=uuid4(),
        email=f"{user_type.value.lower()}-{uuid4().hex[:8]}@example.com",
        password_hash="hash",
        user_type=user_type,
        is_active=True,
    )
    db.add(account)
    db.commit()
    return account


def make_employee(db, account: UserAccount | None = None) -> Employee:
    code = uuid4().hex[:8]
    employee = Employee(
        account_id=account.account_id if account else None,
        emp_code=f"EMP-{code}",
        full_name=f"Employee {code}",
        email=account.email if account else f"emp-{code}@example.com",
        designation="Engineer",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(employee)
    db.commit()
    return employee


def make_project(db) -> Project:
    """Project with its own fresh client and PM (the PM has no login account)."""
    code = uuid4().hex[:8]
    client = Client(company_name=f"Client {code}", contact_person="Contact", email=f"client-{code}@example.com")
    pm = ProjectManager(
        emp_code=f"PM-{code}",
        full_name=f"PM {code}",
        email=f"pm-{code}@example.com",
        date_of_joining=date(2024, 1, 1),
    )
    db.add_all([client, pm])
    db.flush()
    project = Project(
        client_id=client.client_id,
        pm_id=pm.pm_id,
        project_code=f"PRJ-{code}",
        name=f"Project {code}",
        start_date=date(2024, 1, 1),
    )
    db.add(project)
    db.commit()
    return project


def make_team(db, lead: Employee | None = None, project: Project | None = None) -> Team:
    team = Team(
        name=f"Team {uuid4().hex[:8]}",
        lead_emp_id=lead.emp_id if lead else None,
        project_id=project.project_id if project else None,
    )
    db.add(team)
    db.commit()
    return team


def make_task(db, team: Team, assignee: Employee | None = None) -> Task:
    """Task on ``team`` and the team's project (the team must have a project)."""
    task = Task(
        project_id=team.project_id,
        team_id=team.team_id,
        assigned_to=assignee.emp_id if assignee else None,
        title=f"Task {uuid4().hex[:8]}",
    )
    db.add(task)
    db.commit()
    return task


def auth_headers(account: UserAccount) -> dict[str, str]:
    token = create_access_token(data={
        "sub": str(account.account_id),
        "email": account.email,
        "user_type": account.user_type.value,
    })
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Tests
# ==============================================================================

def test_no_invalid_role_literals():
    hits = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if INVALID_ROLE.search(line):
                hits.append(f"{path.relative_to(APP_DIR.parent)}:{lineno}: {line.strip()}")
    assert not hits, "Invalid role literals found:\n" + "\n".join(hits)


def test_team_lead_user_type_can_view_own_team_roster(client, db):
    lead = make_account(db, UserType.TEAM_LEAD)
    team_a = make_team(db, lead=make_employee(db, lead))
    team_b = make_team(db, lead=make_employee(db))
    orphan_lead = make_account(db, UserType.TEAM_LEAD)

    res = client.get(f"/api/v1/teams/{team_a.team_id}/members", headers=auth_headers(lead))
    assert res.status_code == 200

    res = client.get(f"/api/v1/teams/{team_b.team_id}/members", headers=auth_headers(lead))
    assert res.status_code == 403

    res = client.get(f"/api/v1/teams/{team_a.team_id}/members", headers=auth_headers(orphan_lead))
    assert res.status_code == 403


def test_team_lead_can_comment_on_team_task(client, db):
    project = make_project(db)
    lead = make_account(db, UserType.TEAM_LEAD)
    team = make_team(db, lead=make_employee(db, lead), project=project)
    task = make_task(db, team, assignee=make_employee(db, make_account(db, UserType.EMPLOYEE)))
    other_lead = make_account(db, UserType.TEAM_LEAD)
    make_team(db, lead=make_employee(db, other_lead), project=make_project(db))
    url = f"/api/v1/tasks/{task.task_id}/comments"

    res = client.post(url, json={"content": "Lead feedback"}, headers=auth_headers(lead))
    assert res.status_code == 201
    assert res.json()["author_role"] == "TEAM_LEAD"
    comment_id = res.json()["comment_id"]

    res = client.get(url, headers=auth_headers(lead))
    assert res.status_code == 200
    assert comment_id in [c["comment_id"] for c in res.json()]

    assert client.post(url, json={"content": "Nope"}, headers=auth_headers(other_lead)).status_code == 403
    assert client.get(url, headers=auth_headers(other_lead)).status_code == 403


def test_profile_without_employee_row_returns_404(client, db):
    for user_type in (UserType.TEAM_LEAD, UserType.MNC_EXECUTIVE):
        res = client.get("/api/v1/profile/me", headers=auth_headers(make_account(db, user_type)))
        assert res.status_code == 404
        assert res.json()["detail"] == "No employee profile for this account"

    lead = make_account(db, UserType.TEAM_LEAD)
    employee = make_employee(db, lead)
    res = client.get("/api/v1/profile/me", headers=auth_headers(lead))
    assert res.status_code == 200
    assert res.json()["emp_id"] == employee.emp_id


def test_my_tasks_without_employee_row_returns_empty_page(client, db):
    for user_type in (UserType.PM, UserType.MNC_EXECUTIVE):
        res = client.get("/api/v1/tasks/my-tasks", headers=auth_headers(make_account(db, user_type)))
        assert res.status_code == 200
        assert res.json() == {"items": [], "total": 0, "page": 1, "limit": 20}


def test_sysadmin_can_manage_users_and_security(client, db):
    sysadmin = make_account(db, UserType.SYSTEM_ADMIN)
    headers = auth_headers(sysadmin)
    for path in (
        "/api/v1/admin/users",
        "/api/v1/admin/system-params",
        "/api/v1/admin/elevated-access/active",
        "/api/v1/admin/anomaly-alerts",
        "/api/v1/admin/system/backup-status",
    ):
        assert client.get(path, headers=headers).status_code == 200, path

    email = f"new-{uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/admin/users",
        json={"email": email, "password": "Secret123!", "user_type": "EMPLOYEE"},
        headers=headers,
    )
    assert res.status_code == 201
    audit = db.query(AuditLog).filter(
        AuditLog.entity_name == "USER_ACCOUNT",
        AuditLog.entity_ref_id == res.json()["account_id"],
    ).one()
    assert audit.action == AuditAction.CREATE
    assert audit.account_id == sysadmin.account_id

    admin = make_account(db, UserType.ADMIN)
    assert client.get("/api/v1/admin/users", headers=auth_headers(admin)).status_code == 200
    employee = make_account(db, UserType.EMPLOYEE)
    assert client.get("/api/v1/admin/users", headers=auth_headers(employee)).status_code == 403


def test_me_includes_led_team_ids(client, db):
    lead = make_account(db, UserType.TEAM_LEAD)
    lead_emp = make_employee(db, lead)
    team_a = make_team(db, lead=lead_emp)
    team_b = make_team(db, lead=make_employee(db))
    db.add(TeamMember(team_id=team_b.team_id, emp_id=lead_emp.emp_id))
    db.commit()

    body = client.get("/api/v1/auth/me", headers=auth_headers(lead)).json()
    assert "user" not in body
    assert body["account_id"] == str(lead.account_id)
    assert body["email"] == lead.email
    assert body["user_type"] == "TEAM_LEAD"
    assert body["is_active"] is True
    assert "is_mfa_enabled" in body
    assert body["emp_id"] == lead_emp.emp_id
    assert body["led_team_ids"] == [team_a.team_id]
    assert team_b.team_id in body["team_ids"]

    pm = make_account(db, UserType.PM)
    body = client.get("/api/v1/auth/me", headers=auth_headers(pm)).json()
    assert body["emp_id"] is None
    assert body["led_team_ids"] == body["team_ids"] == body["active_elevated_roles"] == []

    employee = make_account(db, UserType.EMPLOYEE)
    admin = make_account(db, UserType.ADMIN)
    now = datetime.now(timezone.utc)
    for role, expires_at, revoked_at in (
        ("PM", now + timedelta(days=1), None),
        ("HR", now - timedelta(hours=1), None),
        ("ADMIN", now + timedelta(days=1), now),
    ):
        db.add(ElevatedAccessGrant(
            user_id=employee.account_id,
            granted_by=admin.account_id,
            granted_role=role,
            reason="test",
            expires_at=expires_at,
            revoked_at=revoked_at,
        ))
    db.commit()
    body = client.get("/api/v1/auth/me", headers=auth_headers(employee)).json()
    assert body["active_elevated_roles"] == ["PM"]
