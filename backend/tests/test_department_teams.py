"""
Unit and Integration tests for HR Department Teams & Team Lead Designation API (US-05, Issue #141).

Covers:
- test_hr_creates_team_and_lead_promoted
- test_duplicate_team_name_in_department_409
- test_lead_change_demotes_previous_lead_when_no_other_team
- test_remove_lead_member_conflict
- test_members_and_lead_notified
- test_project_teams_unaffected
- Role-based access control (HR/Admin allowed, Employee/PM/Client 403, 401 unauthenticated)
- Validation: missing department/employees (404), inactive employees (400)
- Role promotion preserves non-EMPLOYEE roles
- Department team listing with member count and include_disbanded filter
- Partial updates (PUT /teams/{id}) and lead demotion on DISBANDED
- Idempotent member additions
- SQL injection resistance on path parameters
"""

from datetime import date, datetime, timedelta
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.security import create_access_token
from app.models.enums import CommonStatus, TeamStatus, UserType, AuditAction
from app.models.user_account import UserAccount
from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team, TeamMember
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.project import Project
from app.features.departments.router import router as department_router, team_router
from app.features.projects.router import router as project_router


# ==============================================================================
# Fixtures & Isolated In-Memory SQLite Setup
# ==============================================================================

@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            UserAccount.__table__,
            Department.__table__,
            Employee.__table__,
            Team.__table__,
            TeamMember.__table__,
            AuditLog.__table__,
            Notification.__table__,
            Project.__table__,
        ],
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_setup(db_session):
    """Seed prerequisite test entities for Department Teams testing."""
    # 1. Departments
    dept1 = Department(dept_id=1, name="Engineering", description="Core product engineering")
    dept2 = Department(dept_id=2, name="Operations", description="Business operations")
    db_session.add_all([dept1, dept2])
    db_session.commit()

    # 2. User Accounts
    hr_acc = UserAccount(
        account_id=uuid4(),
        email="hr@company.com",
        password_hash="hash",
        user_type=UserType.HR,
        is_active=True,
    )
    admin_acc = UserAccount(
        account_id=uuid4(),
        email="admin@company.com",
        password_hash="hash",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    pm_acc = UserAccount(
        account_id=uuid4(),
        email="pm@company.com",
        password_hash="hash",
        user_type=UserType.PM,
        is_active=True,
    )
    emp_acc1 = UserAccount(
        account_id=uuid4(),
        email="lead1@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp_acc2 = UserAccount(
        account_id=uuid4(),
        email="member2@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp_acc3 = UserAccount(
        account_id=uuid4(),
        email="member3@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    emp_acc4 = UserAccount(
        account_id=uuid4(),
        email="lead2@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    client_acc = UserAccount(
        account_id=uuid4(),
        email="client@clientcorp.com",
        password_hash="hash",
        user_type=UserType.CLIENT,
        is_active=True,
    )

    db_session.add_all([
        hr_acc, admin_acc, pm_acc, emp_acc1, emp_acc2, emp_acc3, emp_acc4, client_acc
    ])
    db_session.commit()

    # 3. Employees
    emp1 = Employee(
        emp_id=10,
        account_id=emp_acc1.account_id,
        dept_id=dept1.dept_id,
        emp_code="EMP-010",
        full_name="Sarah Connor",
        email=emp_acc1.email,
        designation="Software Engineer",
        date_of_joining=date(2023, 1, 15),
        status=CommonStatus.ACTIVE,
    )
    emp2 = Employee(
        emp_id=20,
        account_id=emp_acc2.account_id,
        dept_id=dept1.dept_id,
        emp_code="EMP-020",
        full_name="John Reese",
        email=emp_acc2.email,
        designation="Backend Developer",
        date_of_joining=date(2023, 3, 1),
        status=CommonStatus.ACTIVE,
    )
    emp3 = Employee(
        emp_id=30,
        account_id=emp_acc3.account_id,
        dept_id=dept1.dept_id,
        emp_code="EMP-030",
        full_name="Harold Finch",
        email=emp_acc3.email,
        designation="Security Specialist",
        date_of_joining=date(2023, 4, 1),
        status=CommonStatus.ACTIVE,
    )
    emp_inactive = Employee(
        emp_id=40,
        account_id=None,
        dept_id=dept1.dept_id,
        emp_code="EMP-040",
        full_name="Peter Russo",
        email="russo@company.com",
        designation="Former Specialist",
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.INACTIVE,
    )
    emp4 = Employee(
        emp_id=50,
        account_id=emp_acc4.account_id,
        dept_id=dept1.dept_id,
        emp_code="EMP-050",
        full_name="Marcus Vance",
        email=emp_acc4.email,
        designation="Lead Architect",
        date_of_joining=date(2023, 2, 1),
        status=CommonStatus.ACTIVE,
    )

    db_session.add_all([emp1, emp2, emp3, emp_inactive, emp4])
    db_session.commit()

    def get_auth_header(account: UserAccount) -> dict[str, str]:
        token = create_access_token(
            data={"sub": str(account.account_id), "type": "access"},
            expires_delta=timedelta(hours=1),
        )
        return {"Authorization": f"Bearer {token}"}

    return {
        "hr_headers": get_auth_header(hr_acc),
        "admin_headers": get_auth_header(admin_acc),
        "pm_headers": get_auth_header(pm_acc),
        "emp1_headers": get_auth_header(emp_acc1),
        "client_headers": get_auth_header(client_acc),
        "dept1_id": dept1.dept_id,
        "dept2_id": dept2.dept_id,
        "emp1_id": emp1.emp_id,
        "emp2_id": emp2.emp_id,
        "emp3_id": emp3.emp_id,
        "emp4_id": emp4.emp_id,
        "emp_inactive_id": emp_inactive.emp_id,
        "emp_acc1_id": emp_acc1.account_id,
        "emp_acc2_id": emp_acc2.account_id,
        "emp_acc3_id": emp_acc3.account_id,
        "emp_acc4_id": emp_acc4.account_id,
    }


@pytest.fixture
def client(db_session):
    """FastAPI test client with dependency overrides."""
    app = FastAPI()
    app.include_router(department_router)
    app.include_router(team_router)
    app.include_router(project_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ==============================================================================
# SECTION 1: Required Named Tests (from Issue #141 prompt)
# ==============================================================================

def test_hr_creates_team_and_lead_promoted(client, test_setup, db_session):
    """
    Required Test 1: HR creates a team, lead is automatically added to team
    members, and their UserAccount is promoted from EMPLOYEE to TEAM_LEAD with audit log.
    """
    dept_id = test_setup["dept1_id"]
    lead_id = test_setup["emp1_id"]
    member_ids = [test_setup["emp2_id"], test_setup["emp3_id"]]

    payload = {
        "name": "Payments Squad",
        "description": "Card and wallet integrations",
        "lead_emp_id": lead_id,
        "member_emp_ids": member_ids,
    }

    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json=payload,
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Payments Squad"
    assert data["lead_emp_id"] == lead_id
    assert data["lead_name"] == "Sarah Connor"
    assert data["status"] == "ACTIVE"
    # Member count should be 3 (lead_id + 2 members)
    assert data["member_count"] == 3
    ret_member_ids = [m["employee_id"] for m in data["members"]]
    assert lead_id in ret_member_ids
    assert test_setup["emp2_id"] in ret_member_ids
    assert test_setup["emp3_id"] in ret_member_ids

    # Verify UserAccount promotion
    lead_acc = db_session.get(UserAccount, test_setup["emp_acc1_id"])
    assert lead_acc.user_type == UserType.TEAM_LEAD

    # Verify audit log for USER_ACCOUNT role change
    stmt = select(AuditLog).where(
        AuditLog.entity_name == "USER_ACCOUNT",
        AuditLog.entity_ref_id == str(test_setup["emp_acc1_id"]),
    )
    audit = db_session.scalars(stmt).first()
    assert audit is not None
    assert "EMPLOYEE" in audit.old_value
    assert "TEAM_LEAD" in audit.new_value


def test_duplicate_team_name_in_department_409(client, test_setup):
    """
    Required Test 2: Creating a team with a duplicate name in the same department
    returns 409 Conflict (case-insensitive).
    """
    dept_id = test_setup["dept1_id"]
    payload = {
        "name": "Checkout Alpha",
        "description": "Checkout experience",
        "lead_emp_id": test_setup["emp1_id"],
        "member_emp_ids": [],
    }

    # 1. Create first team
    res1 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json=payload,
        headers=test_setup["hr_headers"],
    )
    assert res1.status_code == 201

    # 2. Try creating second team with case variation
    payload["name"] = "  cHeCkOuT aLpHa  "
    res2 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json=payload,
        headers=test_setup["hr_headers"],
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_lead_change_demotes_previous_lead_when_no_other_team(client, test_setup, db_session):
    """
    Required Test 3: Changing lead to someone else demotes previous lead to EMPLOYEE
    if they lead no other active team.
    """
    dept_id = test_setup["dept1_id"]
    lead1_id = test_setup["emp1_id"]
    lead2_id = test_setup["emp4_id"]

    # 1. Create team with lead 1
    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={
            "name": "Alpha Platform",
            "lead_emp_id": lead1_id,
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 201
    team_id = res.json()["team_id"]

    lead1_acc = db_session.get(UserAccount, test_setup["emp_acc1_id"])
    assert lead1_acc.user_type == UserType.TEAM_LEAD

    # 2. Change lead to lead 2
    res_update = client.put(
        f"/api/v1/teams/{team_id}",
        json={"lead_emp_id": lead2_id},
        headers=test_setup["hr_headers"],
    )
    assert res_update.status_code == 200
    assert res_update.json()["lead_emp_id"] == lead2_id

    # Refresh session
    db_session.expire_all()
    lead1_acc = db_session.get(UserAccount, test_setup["emp_acc1_id"])
    lead2_acc = db_session.get(UserAccount, test_setup["emp_acc4_id"])

    # Previous lead demoted to EMPLOYEE
    assert lead1_acc.user_type == UserType.EMPLOYEE
    # New lead promoted to TEAM_LEAD
    assert lead2_acc.user_type == UserType.TEAM_LEAD


def test_remove_lead_member_conflict(client, test_setup):
    """
    Required Test 4: Removing the designated lead from team members returns 409 Conflict.
    """
    dept_id = test_setup["dept1_id"]
    lead_id = test_setup["emp1_id"]

    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={
            "name": "Core Security",
            "lead_emp_id": lead_id,
            "member_emp_ids": [test_setup["emp2_id"]],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 201
    team_id = res.json()["team_id"]

    # Try removing lead -> 409
    res_del = client.delete(
        f"/api/v1/teams/{team_id}/members/{lead_id}",
        headers=test_setup["hr_headers"],
    )
    assert res_del.status_code == 409
    assert "cannot remove lead" in res_del.json()["detail"].lower()


def test_members_and_lead_notified(client, test_setup, db_session):
    """
    Required Test 5: Notifications created via NotificationService:
    - Member added: 'You joined {team.name}' (TEAM_MEMBER_ADDED)
    - Made lead: 'You are now team lead of {team.name}' (TEAM_LEAD_ASSIGNED)
    - Lead notified when members join team.
    """
    dept_id = test_setup["dept1_id"]
    lead_id = test_setup["emp1_id"]
    member_id = test_setup["emp2_id"]

    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={
            "name": "Integration Squad",
            "lead_emp_id": lead_id,
            "member_emp_ids": [member_id],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 201

    # Check lead notification
    lead_notif = db_session.scalars(
        select(Notification).where(
            Notification.account_id == test_setup["emp_acc1_id"],
            Notification.type == "TEAM_LEAD_ASSIGNED",
        )
    ).first()
    assert lead_notif is not None
    assert "team lead of Integration Squad" in lead_notif.message

    # Check member notification
    member_notif = db_session.scalars(
        select(Notification).where(
            Notification.account_id == test_setup["emp_acc2_id"],
            Notification.type == "TEAM_MEMBER_ADDED",
        )
    ).first()
    assert member_notif is not None
    assert "You joined Integration Squad" in member_notif.message


def test_project_teams_unaffected(client, test_setup, db_session):
    """
    Required Test 6: Project teams (with project_id and nullable dept_id) keep working unchanged.
    """
    # Create a project directly in DB
    proj = Project(
        project_id=101,
        project_code="PRJ-101",
        name="Enterprise Workflow Suite",
        client_id=1,
        pm_id=1,
        start_date=date(2024, 1, 1),
    )
    db_session.add(proj)
    db_session.commit()

    # Create team with project_id and dept_id=None
    team = Team(
        team_id=202,
        project_id=proj.project_id,
        dept_id=None,
        name="Project Squad Beta",
        lead_emp_id=test_setup["emp1_id"],
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.commit()

    # Query project team via GET /teams/{id}/members (from US-37)
    res = client.get(
        f"/api/v1/teams/{team.team_id}/members",
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ==============================================================================
# SECTION 2: Role-Based Access Control (RBAC) & Authentication Tests
# ==============================================================================

def test_admin_creates_team_success(client, test_setup):
    """SysAdmin (ADMIN) role is authorized to create department teams."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Admin Managed Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["admin_headers"],
    )
    assert res.status_code == 201


def test_employee_creates_team_forbidden_403(client, test_setup):
    """EMPLOYEE role is forbidden from creating department teams -> 403."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Employee Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["emp1_headers"],
    )
    assert res.status_code == 403


def test_pm_creates_team_forbidden_403(client, test_setup):
    """PM role is forbidden from creating department teams (HR/Admin only) -> 403."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "PM Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["pm_headers"],
    )
    assert res.status_code == 403


def test_client_creates_team_forbidden_403(client, test_setup):
    """CLIENT role is forbidden from department endpoints -> 403."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Client Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["client_headers"],
    )
    assert res.status_code == 403


def test_unauthenticated_creates_team_401(client, test_setup):
    """Missing Bearer token returns 401 Unauthorized."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Anon Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
    )
    assert res.status_code == 401


# ==============================================================================
# SECTION 3: Input Validation & Boundary Tests (404, 400, 409)
# ==============================================================================

def test_create_team_missing_department_404(client, test_setup):
    """404 if department does not exist."""
    res = client.post(
        "/api/v1/departments/99999/teams",
        json={
            "name": "Orphan Team",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 404
    assert "department with id 99999 not found" in res.json()["detail"].lower()


def test_create_team_missing_lead_employee_404(client, test_setup):
    """404 if designated lead employee does not exist."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Ghost Lead Team",
            "lead_emp_id": 99999,
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 404
    assert "employee with id 99999 not found" in res.json()["detail"].lower()


def test_create_team_inactive_lead_employee_400(client, test_setup):
    """400 if designated lead employee is inactive."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Inactive Lead Team",
            "lead_emp_id": test_setup["emp_inactive_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 400
    assert "inactive" in res.json()["detail"].lower()


def test_create_team_missing_member_employee_404(client, test_setup):
    """404 if any employee in member_emp_ids does not exist."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Bad Member Team",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [test_setup["emp2_id"], 99999],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 404


def test_create_team_inactive_member_employee_400(client, test_setup):
    """400 if any employee in member_emp_ids is inactive."""
    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Inactive Member Team",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [test_setup["emp_inactive_id"]],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 400
    assert "inactive" in res.json()["detail"].lower()


def test_lead_keeps_existing_role_if_not_employee(client, test_setup, db_session):
    """
    If the designated lead has an account with a role other than EMPLOYEE
    (e.g., ADMIN or PM), they keep their existing role.
    """
    # Create employee linked to ADMIN account
    admin_acc = db_session.scalars(
        select(UserAccount).where(UserAccount.user_type == UserType.ADMIN)
    ).first()
    admin_emp = Employee(
        emp_id=99,
        account_id=admin_acc.account_id,
        dept_id=test_setup["dept1_id"],
        emp_code="EMP-ADMIN-99",
        full_name="Admin Person",
        email=admin_acc.email,
        designation="Admin Lead",
        date_of_joining=date(2023, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add(admin_emp)
    db_session.commit()

    res = client.post(
        f"/api/v1/departments/{test_setup['dept1_id']}/teams",
        json={
            "name": "Admin Led Team",
            "lead_emp_id": admin_emp.emp_id,
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res.status_code == 201

    # Verify admin_acc is STILL ADMIN, not overwritten
    db_session.expire_all()
    refreshed_admin = db_session.get(UserAccount, admin_acc.account_id)
    assert refreshed_admin.user_type == UserType.ADMIN


def test_same_team_name_in_different_department_allowed(client, test_setup):
    """
    Unique names rule: team names are unique PER department.
    Creating the same name in different departments is allowed.
    """
    dept1 = test_setup["dept1_id"]
    dept2 = test_setup["dept2_id"]

    res1 = client.post(
        f"/api/v1/departments/{dept1}/teams",
        json={
            "name": "DevOps Squad",
            "lead_emp_id": test_setup["emp1_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"/api/v1/departments/{dept2}/teams",
        json={
            "name": "DevOps Squad",
            "lead_emp_id": test_setup["emp4_id"],
            "member_emp_ids": [],
        },
        headers=test_setup["hr_headers"],
    )
    assert res2.status_code == 201


# ==============================================================================
# SECTION 4: Listing, Updating, Member Add/Remove Tests
# ==============================================================================

def test_get_department_teams_defaults_to_active(client, test_setup):
    """GET /departments/{dept_id}/teams returns only ACTIVE teams by default."""
    dept_id = test_setup["dept1_id"]

    # Create team 1
    res1 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Active Team A", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    t1_id = res1.json()["team_id"]

    # Create team 2 and disband it
    res2 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Disbanded Team B", "lead_emp_id": test_setup["emp4_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    t2_id = res2.json()["team_id"]
    client.put(
        f"/api/v1/teams/{t2_id}",
        json={"status": "DISBANDED"},
        headers=test_setup["hr_headers"],
    )

    # GET default -> only Active Team A
    list_res = client.get(
        f"/api/v1/departments/{dept_id}/teams",
        headers=test_setup["hr_headers"],
    )
    assert list_res.status_code == 200
    team_ids = [t["team_id"] for t in list_res.json()]
    assert t1_id in team_ids
    assert t2_id not in team_ids


def test_get_department_teams_include_disbanded(client, test_setup):
    """GET /departments/{dept_id}/teams?include_disbanded=true includes disbanded teams."""
    dept_id = test_setup["dept1_id"]

    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Disbanded Team C", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    t_id = res.json()["team_id"]
    client.put(
        f"/api/v1/teams/{t_id}",
        json={"status": "DISBANDED"},
        headers=test_setup["hr_headers"],
    )

    list_res = client.get(
        f"/api/v1/departments/{dept_id}/teams?include_disbanded=true",
        headers=test_setup["hr_headers"],
    )
    assert list_res.status_code == 200
    team_ids = [t["team_id"] for t in list_res.json()]
    assert t_id in team_ids


def test_get_department_teams_nonexistent_department_404(client, test_setup):
    """GET /departments/{dept_id}/teams for non-existent dept returns 404."""
    res = client.get("/api/v1/departments/99999/teams", headers=test_setup["hr_headers"])
    assert res.status_code == 404


def test_put_update_team_name_and_description(client, test_setup):
    """PUT /teams/{team_id} allows partial update of name and description."""
    dept_id = test_setup["dept1_id"]
    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Original Name", "description": "Original Desc", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    team_id = res.json()["team_id"]

    update_res = client.put(
        f"/api/v1/teams/{team_id}",
        json={"name": "Updated Name", "description": "Updated Desc"},
        headers=test_setup["hr_headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Updated Name"
    assert update_res.json()["description"] == "Updated Desc"


def test_put_update_team_duplicate_name_409(client, test_setup):
    """PUT /teams/{team_id} with name conflicting with another team in dept returns 409."""
    dept_id = test_setup["dept1_id"]
    client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Team One", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    res2 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Team Two", "lead_emp_id": test_setup["emp4_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    t2_id = res2.json()["team_id"]

    # Try renaming Team Two to Team One
    put_res = client.put(
        f"/api/v1/teams/{t2_id}",
        json={"name": "Team One"},
        headers=test_setup["hr_headers"],
    )
    assert put_res.status_code == 409


def test_put_disband_team_demotes_lead_if_no_other_teams(client, test_setup, db_session):
    """Disbanding a team demotes lead to EMPLOYEE if they lead no other active team."""
    dept_id = test_setup["dept1_id"]
    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Sole Squad", "lead_emp_id": test_setup["emp4_id"], "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    team_id = res.json()["team_id"]

    lead4_acc = db_session.get(UserAccount, test_setup["emp_acc4_id"])
    assert lead4_acc.user_type == UserType.TEAM_LEAD

    # Disband team
    client.put(
        f"/api/v1/teams/{team_id}",
        json={"status": "DISBANDED"},
        headers=test_setup["hr_headers"],
    )

    db_session.expire_all()
    lead4_acc = db_session.get(UserAccount, test_setup["emp_acc4_id"])
    assert lead4_acc.user_type == UserType.EMPLOYEE


def test_put_disband_team_does_not_demote_if_leads_other_active_team(client, test_setup, db_session):
    """Disbanding a team does NOT demote lead if they lead another active team."""
    dept_id = test_setup["dept1_id"]
    lead_id = test_setup["emp4_id"]

    # Create team 1
    res1 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Active Squad 1", "lead_emp_id": lead_id, "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    # Create team 2
    res2 = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Active Squad 2", "lead_emp_id": lead_id, "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )

    # Disband team 1
    client.put(
        f"/api/v1/teams/{res1.json()['team_id']}",
        json={"status": "DISBANDED"},
        headers=test_setup["hr_headers"],
    )

    db_session.expire_all()
    lead_acc = db_session.get(UserAccount, test_setup["emp_acc4_id"])
    # Still leads Active Squad 2, so remains TEAM_LEAD
    assert lead_acc.user_type == UserType.TEAM_LEAD


def test_post_add_team_members_idempotent(client, test_setup):
    """POST /teams/{team_id}/members is idempotent."""
    dept_id = test_setup["dept1_id"]
    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Idempotent Squad", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": [test_setup["emp2_id"]]},
        headers=test_setup["hr_headers"],
    )
    team_id = res.json()["team_id"]

    # Add member 2 again (already member) and member 3 (new)
    res_add = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"emp_ids": [test_setup["emp2_id"], test_setup["emp3_id"]]},
        headers=test_setup["hr_headers"],
    )
    assert res_add.status_code == 200
    data = res_add.json()
    assert data["member_count"] == 3  # lead (1) + member 2 + member 3


def test_delete_remove_regular_member_success(client, test_setup):
    """DELETE /teams/{team_id}/members/{emp_id} successfully removes regular member."""
    dept_id = test_setup["dept1_id"]
    member_id = test_setup["emp2_id"]
    res = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Trim Squad", "lead_emp_id": test_setup["emp1_id"], "member_emp_ids": [member_id]},
        headers=test_setup["hr_headers"],
    )
    team_id = res.json()["team_id"]

    res_del = client.delete(
        f"/api/v1/teams/{team_id}/members/{member_id}",
        headers=test_setup["hr_headers"],
    )
    assert res_del.status_code == 204


def test_sqli_in_department_and_team_endpoints(client, test_setup):
    """SQL injection probes in path parameters rejected with 422 Unprocessable Entity."""
    # 1. Dept teams path SQLi
    res1 = client.get("/api/v1/departments/'%20OR%201=1%20--/teams", headers=test_setup["hr_headers"])
    assert res1.status_code == 422

    # 2. Team update path SQLi
    res2 = client.put("/api/v1/teams/1;%20DROP%20TABLE%20team;--", json={"name": "x"}, headers=test_setup["hr_headers"])
    assert res2.status_code == 422

    # 3. Team member delete path SQLi
    res3 = client.delete("/api/v1/teams/1/members/1%20UNION%20SELECT%201", headers=test_setup["hr_headers"])
    assert res3.status_code == 422


def test_client_list_department_teams_forbidden_403(client, test_setup):
    """CLIENT role cannot list department teams (returns 403 Forbidden)."""
    dept_id = test_setup["dept1_id"]
    res = client.get(
        f"/api/v1/departments/{dept_id}/teams",
        headers=test_setup["client_headers"],
    )
    assert res.status_code == 403


def test_reactivate_disbanded_team_promotes_lead(client, test_setup, db_session):
    """Reactivating a disbanded team re-promotes lead to TEAM_LEAD if their account is EMPLOYEE."""
    dept_id = test_setup["dept1_id"]
    lead_id = test_setup["emp1_id"]
    lead_acc_id = test_setup["emp_acc1_id"]

    # 1. Create team -> lead promoted to TEAM_LEAD
    res_create = client.post(
        f"/api/v1/departments/{dept_id}/teams",
        json={"name": "Reactivate Test Squad", "lead_emp_id": lead_id, "member_emp_ids": []},
        headers=test_setup["hr_headers"],
    )
    assert res_create.status_code == 201
    team_id = res_create.json()["team_id"]

    account = db_session.query(UserAccount).filter(UserAccount.account_id == lead_acc_id).first()
    assert account.user_type == UserType.TEAM_LEAD

    # 2. Disband team -> lead demoted to EMPLOYEE
    res_disband = client.put(
        f"/api/v1/teams/{team_id}",
        json={"status": "DISBANDED"},
        headers=test_setup["hr_headers"],
    )
    assert res_disband.status_code == 200

    account = db_session.query(UserAccount).filter(UserAccount.account_id == lead_acc_id).first()
    assert account.user_type == UserType.EMPLOYEE

    # 3. Reactivate team (DISBANDED -> ACTIVE) -> lead promoted back to TEAM_LEAD
    res_reactivate = client.put(
        f"/api/v1/teams/{team_id}",
        json={"status": "ACTIVE"},
        headers=test_setup["hr_headers"],
    )
    assert res_reactivate.status_code == 200

    account = db_session.query(UserAccount).filter(UserAccount.account_id == lead_acc_id).first()
    assert account.user_type == UserType.TEAM_LEAD

