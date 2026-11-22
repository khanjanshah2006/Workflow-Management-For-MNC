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
from app.models.enums import AuditAction, TeamStatus, UserType
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


def make_project(db, pm: ProjectManager | None = None, client: Client | None = None) -> Project:
    """Project for ``pm`` and ``client``; each defaults to a fresh login-less row."""
    code = uuid4().hex[:8]
    if client is None:
        client = Client(company_name=f"Client {code}", contact_person="Contact", email=f"client-{code}@example.com")
    if pm is None:
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


def test_disbanded_team_lead_cannot_read_task_comments(client, db):
    project = make_project(db)
    team = make_team(db, project=project)
    task = make_task(db, team, assignee=make_employee(db, make_account(db, UserType.EMPLOYEE)))
    lead = make_account(db, UserType.TEAM_LEAD)
    old_team = make_team(db, lead=make_employee(db, lead), project=project)
    url = f"/api/v1/tasks/{task.task_id}/comments"
    assert client.get(url, headers=auth_headers(lead)).status_code == 200

    old_team.status = TeamStatus.DISBANDED
    db.commit()
    assert client.get(url, headers=auth_headers(lead)).status_code == 403


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


def test_admin_endpoints_block_self_escalation(client, db):
    sysadmin = make_account(db, UserType.SYSTEM_ADMIN)
    admin = make_account(db, UserType.ADMIN)
    headers = auth_headers(sysadmin)

    def patch_role(actor_headers, target, user_type):
        return client.patch(
            f"/api/v1/admin/users/{target.account_id}/role",
            json={"user_type": user_type},
            headers=actor_headers,
        )

    def grant(target, role):
        return client.post(
            "/api/v1/admin/elevated-access",
            json={
                "user_id": str(target.account_id),
                "granted_role": role,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "reason": "Escalation test",
            },
            headers=headers,
        )

    def audit_count():
        return db.query(AuditLog).filter(AuditLog.account_id == sysadmin.account_id).count()

    before = audit_count()
    res = patch_role(headers, sysadmin, "ADMIN")
    assert res.status_code == 403
    assert res.json()["detail"] == "You cannot change your own role"
    db.refresh(sysadmin)
    assert sysadmin.user_type == UserType.SYSTEM_ADMIN

    target = make_account(db, UserType.EMPLOYEE)
    res = patch_role(headers, target, "ADMIN")
    assert res.status_code == 403
    assert res.json()["detail"] == "Only ADMIN can assign the ADMIN role"

    for role in ("ADMIN", "PM"):
        assert grant(sysadmin, role).status_code == 403
    res = grant(target, " admin ")
    assert res.status_code == 403
    assert res.json()["detail"] == "Only ADMIN can assign the ADMIN role"
    assert audit_count() == before
    assert db.query(ElevatedAccessGrant).filter(ElevatedAccessGrant.granted_by == sysadmin.account_id).count() == 0

    assert patch_role(headers, target, "PM").status_code == 200
    assert patch_role(headers, target, "EMPLOYEE").status_code == 200
    res = grant(target, "PM")
    assert res.status_code == 201
    assert res.json()["granted_role"] == "PM"

    admin_headers = auth_headers(admin)
    assert patch_role(admin_headers, target, "ADMIN").status_code == 200
    assert patch_role(admin_headers, admin, "EMPLOYEE").status_code == 403

    def create_user(actor_headers, user_type, email=None):
        return client.post(
            "/api/v1/admin/users",
            json={"email": email or f"new-{uuid4().hex[:8]}@example.com", "password": "Secret123!", "user_type": user_type},
            headers=actor_headers,
        )

    before = audit_count()
    email = f"new-{uuid4().hex[:8]}@example.com"
    res = create_user(headers, "ADMIN", email)
    assert res.status_code == 403
    assert res.json()["detail"] == "Only ADMIN can assign the ADMIN role"
    assert db.query(UserAccount).filter(UserAccount.email == email).count() == 0
    assert audit_count() == before
    # Permission is checked before the duplicate-email conflict.
    assert create_user(headers, "ADMIN", target.email).status_code == 403
    assert create_user(headers, "EMPLOYEE").status_code == 201
    assert create_user(admin_headers, "ADMIN").status_code == 201


# ==============================================================================
# Role x endpoint matrix
# ==============================================================================

INTERNAL_ROLES = frozenset(UserType) - {UserType.CLIENT}
PLATFORM_ADMINS = frozenset({UserType.ADMIN, UserType.SYSTEM_ADMIN})


@pytest.fixture(scope="module")
def matrix_seed(session_factory):
    """One account per role, plus a project/team/task wired to the PM, TEAM_LEAD and EMPLOYEE."""
    db = session_factory()
    try:
        accounts = {user_type: make_account(db, user_type) for user_type in UserType}
        employees = {
            user_type: make_employee(db, accounts[user_type])
            for user_type in UserType
            if user_type is not UserType.CLIENT
        }
        pm_account = accounts[UserType.PM]
        pm = ProjectManager(
            account_id=pm_account.account_id,
            emp_code=f"PM-{uuid4().hex[:8]}",
            full_name="Matrix PM",
            email=pm_account.email,
            date_of_joining=date(2024, 1, 1),
        )
        client_account = accounts[UserType.CLIENT]
        client_row = Client(
            account_id=client_account.account_id,
            company_name="Matrix Client",
            contact_person="Contact",
            email=client_account.email,
        )
        project = make_project(db, pm=pm, client=client_row)
        team = make_team(db, lead=employees[UserType.TEAM_LEAD], project=project)
        task = make_task(db, team, assignee=employees[UserType.EMPLOYEE])
        yield {
            "headers": {user_type: auth_headers(account) for user_type, account in accounts.items()},
            "team_id": team.team_id,
            "task_id": task.task_id,
        }
    finally:
        db.close()


# (method, path template, roles that succeed, success status)
MATRIX = [
    ("GET", "/api/v1/teams/{team_id}/members",
     {UserType.HR, UserType.ADMIN, UserType.PM, UserType.TEAM_LEAD}, 200),
    ("GET", "/api/v1/tasks/{task_id}/comments",
     {UserType.EMPLOYEE, UserType.TEAM_LEAD, UserType.PM, UserType.ADMIN, UserType.SYSTEM_ADMIN}, 200),
    ("GET", "/api/v1/profile/me", INTERNAL_ROLES, 200),
    ("GET", "/api/v1/admin/users", PLATFORM_ADMINS, 200),
    ("GET", "/api/v1/admin/system-params", PLATFORM_ADMINS, 200),
    ("GET", "/api/v1/admin/elevated-access/active", PLATFORM_ADMINS, 200),
    ("GET", "/api/v1/admin/anomaly-alerts", PLATFORM_ADMINS, 200),
    ("GET", "/api/v1/admin/system/backup-status", PLATFORM_ADMINS, 200),
    ("POST", "/api/v1/departments", {UserType.HR, UserType.ADMIN}, 201),
    ("GET", "/api/v1/tasks/my-tasks", INTERNAL_ROLES, 200),
    ("GET", "/api/v1/auth/me", set(UserType), 200),
]

MATRIX_CASES = [
    pytest.param(method, path, allowed, success, user_type, id=f"{method} {path} as {user_type.value}")
    for method, path, allowed, success in MATRIX
    for user_type in UserType
]


@pytest.mark.parametrize("method,path,allowed,success,user_type", MATRIX_CASES)
def test_rbac_matrix(client, matrix_seed, method, path, allowed, success, user_type):
    url = path.format(team_id=matrix_seed["team_id"], task_id=matrix_seed["task_id"])
    kwargs = {"headers": matrix_seed["headers"][user_type]}
    if method == "POST":
        kwargs["json"] = {"name": f"Dept {user_type.value} {uuid4().hex[:8]}"}

    res = client.request(method, url, **kwargs)

    expected = success if user_type in allowed else 403
    assert res.status_code == expected, res.text
