"""
Unit and Integration tests for Team Members Roster and Team Tasks Query Endpoints (US-37).

Covers:
- Team Lead authorized query on their own assigned team (GET /members and GET /tasks)
- US-37 exact response schema verification (employee_id, emp_code, full_name, email, designation)
- HR and SysAdmin unrestricted read access across teams
- Project Manager query access
- Clean empty array [] response when team has no assigned members
- Filtering to only ACTIVE employees (INACTIVE members excluded)
- 403 Forbidden for Team Lead querying other teams they do not lead
- 403 Forbidden for non-lead employees
- 403 Forbidden for Client role accounts
- 403 Forbidden when employee account has no linked employee profile
- 404 Not Found for non-existent team IDs
- 401 Unauthorized for unauthenticated requests and invalid/expired JWT tokens
- Tasks stub endpoint returning [] until S3
- SQL injection resistance in path parameters (strict integer coercion -> 422)
- Boundary and edge case testing (negative and zero IDs -> 404)
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.security import create_access_token
from app.models.enums import CommonStatus, TeamStatus, UserType
from app.models.user_account import UserAccount
from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team, TeamMember
from app.features.departments.router import team_router


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
    """Seed prerequisite test entities for US-37 testing."""
    # 1. Department
    dept = Department(dept_id=1, name="Core Engineering", description="Engineering division")
    db_session.add(dept)
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
    lead_acc = UserAccount(
        account_id=uuid4(),
        email="lead@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    lead2_acc = UserAccount(
        account_id=uuid4(),
        email="lead2@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    member_acc = UserAccount(
        account_id=uuid4(),
        email="member@company.com",
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
    no_emp_acc = UserAccount(
        account_id=uuid4(),
        email="orphan@company.com",
        password_hash="hash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )

    db_session.add_all([
        hr_acc, admin_acc, pm_acc, lead_acc, lead2_acc, member_acc, client_acc, no_emp_acc
    ])
    db_session.commit()

    # 3. Employees
    emp_lead = Employee(
        emp_id=1,
        account_id=lead_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-LEAD-01",
        full_name="Sarah Connor",
        email=lead_acc.email,
        designation="Technical Lead",
        date_of_joining=date(2023, 1, 15),
        status=CommonStatus.ACTIVE,
    )
    emp_member1 = Employee(
        emp_id=2,
        account_id=member_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-DEV-02",
        full_name="John Reese",
        email=member_acc.email,
        designation="Senior Backend Engineer",
        date_of_joining=date(2023, 3, 1),
        status=CommonStatus.ACTIVE,
    )
    emp_member2 = Employee(
        emp_id=3,
        account_id=None,
        dept_id=dept.dept_id,
        emp_code="EMP-QA-03",
        full_name="Harold Finch",
        email="finch@company.com",
        designation="QA Architect",
        date_of_joining=date(2023, 4, 1),
        status=CommonStatus.ACTIVE,
    )
    emp_inactive = Employee(
        emp_id=4,
        account_id=None,
        dept_id=dept.dept_id,
        emp_code="EMP-INACT-04",
        full_name="Peter Russo",
        email="russo@company.com",
        designation="Former Consultant",
        date_of_joining=date(2022, 1, 1),
        status=CommonStatus.INACTIVE,
    )
    emp_lead2 = Employee(
        emp_id=5,
        account_id=lead2_acc.account_id,
        dept_id=dept.dept_id,
        emp_code="EMP-LEAD-05",
        full_name="Marcus Vance",
        email=lead2_acc.email,
        designation="Infra Lead",
        date_of_joining=date(2023, 2, 1),
        status=CommonStatus.ACTIVE,
    )

    db_session.add_all([emp_lead, emp_member1, emp_member2, emp_inactive, emp_lead2])
    db_session.commit()

    # 4. Teams
    # Team 1: Led by emp_lead (emp_id 1), has 2 active members (2, 3) and 1 inactive member (4)
    team1 = Team(
        team_id=1,
        name="Backend Core Alpha",
        description="Core workflow and distributed backend squad",
        lead_emp_id=emp_lead.emp_id,
        status=TeamStatus.ACTIVE,
    )
    # Team 2: Led by emp_lead2 (emp_id 5)
    team2 = Team(
        team_id=2,
        name="Infra Squad Bravo",
        description="Cloud infrastructure and DevOps",
        lead_emp_id=emp_lead2.emp_id,
        status=TeamStatus.ACTIVE,
    )
    # Team 3: Led by emp_lead (emp_id 1) but has NO assigned members
    team3 = Team(
        team_id=3,
        name="Greenfield Delta",
        description="Freshly chartered team with zero members",
        lead_emp_id=emp_lead.emp_id,
        status=TeamStatus.ACTIVE,
    )

    db_session.add_all([team1, team2, team3])
    db_session.commit()

    # 5. Team Memberships
    tm1 = TeamMember(team_id=team1.team_id, emp_id=emp_member1.emp_id, joined_on=date(2023, 3, 1))
    tm2 = TeamMember(team_id=team1.team_id, emp_id=emp_member2.emp_id, joined_on=date(2023, 4, 1))
    tm3 = TeamMember(team_id=team1.team_id, emp_id=emp_inactive.emp_id, joined_on=date(2023, 5, 1))
    tm4 = TeamMember(team_id=team2.team_id, emp_id=emp_lead2.emp_id, joined_on=date(2023, 2, 1))

    db_session.add_all([tm1, tm2, tm3, tm4])
    db_session.commit()

    # Helper function to generate auth headers
    def get_auth_header(account: UserAccount, expired: bool = False) -> dict[str, str]:
        delta = timedelta(hours=-1) if expired else timedelta(hours=1)
        token = create_access_token(
            data={"sub": str(account.account_id), "type": "access"},
            expires_delta=delta,
        )
        return {"Authorization": f"Bearer {token}"}

    return {
        "hr_headers": get_auth_header(hr_acc),
        "admin_headers": get_auth_header(admin_acc),
        "pm_headers": get_auth_header(pm_acc),
        "lead_headers": get_auth_header(lead_acc),
        "lead2_headers": get_auth_header(lead2_acc),
        "member_headers": get_auth_header(member_acc),
        "client_headers": get_auth_header(client_acc),
        "orphan_headers": get_auth_header(no_emp_acc),
        "expired_headers": get_auth_header(lead_acc, expired=True),
        "team1_id": team1.team_id,
        "team2_id": team2.team_id,
        "team3_empty_id": team3.team_id,
    }


@pytest.fixture
def client(db_session):
    """FastAPI test client with get_db dependency overridden to SQLite in-memory."""
    app = FastAPI()
    app.include_router(team_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ==============================================================================
# SECTION 1: Happy Path & Acceptance Criteria Tests
# ==============================================================================

def test_get_team_members_team_lead_own_team_success(client, test_setup):
    """AC 1: Team Lead can query their own assigned team -> 200 OK."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["lead_headers"])
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2  # Only active members (John Reese and Harold Finch)


def test_get_team_members_schema_fields(client, test_setup):
    """US-37: Returns employee_id, emp_code, full_name, email, designation."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["lead_headers"])
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    first = data[0]
    expected_keys = {"employee_id", "emp_code", "full_name", "email", "designation"}
    assert set(first.keys()) == expected_keys
    assert first["employee_id"] == 2
    assert first["emp_code"] == "EMP-DEV-02"
    assert first["full_name"] == "John Reese"
    assert first["email"] == "member@company.com"
    assert first["designation"] == "Senior Backend Engineer"


def test_get_team_members_hr_manager_success(client, test_setup):
    """AC 2: HR can query any team's roster -> 200 OK."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["hr_headers"])
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_team_members_sysadmin_success(client, test_setup):
    """AC 2: SysAdmin can query any team's roster -> 200 OK."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["admin_headers"])
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_team_members_pm_success(client, test_setup):
    """Project Manager can query any team's roster for project staffing -> 200 OK."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["pm_headers"])
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_team_members_empty_team_returns_empty_array(client, test_setup):
    """AC 3: Returns empty array cleanly if team has no members assigned."""
    empty_team_id = test_setup["team3_empty_id"]
    res = client.get(f"/api/v1/teams/{empty_team_id}/members", headers=test_setup["lead_headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_get_team_members_filters_out_inactive_employees(client, test_setup):
    """US-37 Scope: Queries employee joining on team_member where status = ACTIVE."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members", headers=test_setup["admin_headers"])
    assert res.status_code == 200
    emp_ids = [m["employee_id"] for m in res.json()]
    # emp_id 4 is INACTIVE and must NOT be in returned roster
    assert 4 not in emp_ids
    assert 2 in emp_ids
    assert 3 in emp_ids


# ==============================================================================
# SECTION 2: Role-Based Access Control (RBAC) & Scope Guarding
# ==============================================================================

def test_get_team_members_team_lead_forbidden_on_other_team(client, test_setup):
    """AC 1: 403 Forbidden if Team Lead queries other teams."""
    team2_id = test_setup["team2_id"]  # Led by Lead 2, not Lead 1
    res = client.get(f"/api/v1/teams/{team2_id}/members", headers=test_setup["lead_headers"])
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


def test_get_team_members_non_lead_employee_forbidden(client, test_setup):
    """Regular employee (non-lead) querying team roster is rejected with 403 Forbidden."""
    team1_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team1_id}/members", headers=test_setup["member_headers"])
    assert res.status_code == 403


def test_get_team_members_client_role_forbidden(client, test_setup):
    """Client role querying internal team roster is rejected with 403 Forbidden."""
    team1_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team1_id}/members", headers=test_setup["client_headers"])
    assert res.status_code == 403


def test_get_team_members_employee_without_profile_forbidden(client, test_setup):
    """UserAccount with EMPLOYEE type but no linked employee record rejected with 403."""
    team1_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team1_id}/members", headers=test_setup["orphan_headers"])
    assert res.status_code == 403


# ==============================================================================
# SECTION 3: Authentication & Token Integrity (401)
# ==============================================================================

def test_get_team_members_unauthenticated_401(client, test_setup):
    """Request missing Authorization header returns 401 Unauthorized."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/members")
    assert res.status_code == 401


def test_get_team_members_invalid_token_401(client, test_setup):
    """Request with malformed or tampered token returns 401 Unauthorized."""
    team_id = test_setup["team1_id"]
    res = client.get(
        f"/api/v1/teams/{team_id}/members",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert res.status_code == 401


def test_get_team_members_expired_token_401(client, test_setup):
    """Request with expired JWT token returns 401 Unauthorized."""
    team_id = test_setup["team1_id"]
    res = client.get(
        f"/api/v1/teams/{team_id}/members",
        headers=test_setup["expired_headers"],
    )
    assert res.status_code == 401


# ==============================================================================
# SECTION 4: Team Tasks Stub Endpoints (US-37)
# ==============================================================================

def test_get_team_tasks_team_lead_success(client, test_setup):
    """US-37: GET /api/v1/teams/{id}/tasks stub returning [] until S3 tasks land."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/tasks", headers=test_setup["lead_headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_get_team_tasks_hr_success(client, test_setup):
    """HR can query team tasks stub -> 200 OK with []."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/tasks", headers=test_setup["hr_headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_get_team_tasks_admin_success(client, test_setup):
    """SysAdmin can query team tasks stub -> 200 OK with []."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/tasks", headers=test_setup["admin_headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_get_team_tasks_pm_success(client, test_setup):
    """Project Manager can query team tasks stub -> 200 OK with []."""
    team_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team_id}/tasks", headers=test_setup["pm_headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_get_team_tasks_team_lead_other_team_forbidden(client, test_setup):
    """Team Lead cannot query tasks of another team -> 403 Forbidden."""
    team2_id = test_setup["team2_id"]
    res = client.get(f"/api/v1/teams/{team2_id}/tasks", headers=test_setup["lead_headers"])
    assert res.status_code == 403


def test_get_team_tasks_non_lead_employee_forbidden(client, test_setup):
    """Non-lead employee cannot query team tasks -> 403 Forbidden."""
    team1_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team1_id}/tasks", headers=test_setup["member_headers"])
    assert res.status_code == 403


def test_get_team_tasks_client_forbidden(client, test_setup):
    """Client cannot query team tasks -> 403 Forbidden."""
    team1_id = test_setup["team1_id"]
    res = client.get(f"/api/v1/teams/{team1_id}/tasks", headers=test_setup["client_headers"])
    assert res.status_code == 403


def test_get_team_tasks_nonexistent_team_404(client, test_setup):
    """Querying tasks for nonexistent team ID returns 404 Not Found."""
    res = client.get("/api/v1/teams/99999/tasks", headers=test_setup["admin_headers"])
    assert res.status_code == 404


# ==============================================================================
# SECTION 5: Missing Entity / Not Found (404)
# ==============================================================================

def test_get_team_members_nonexistent_team_404(client, test_setup):
    """Querying members for non-existent team ID returns 404 Not Found."""
    res = client.get("/api/v1/teams/99999/members", headers=test_setup["admin_headers"])
    assert res.status_code == 404
    assert "99999" in res.json()["detail"]


# ==============================================================================
# SECTION 6: Defensive Security & SQL Injection Resistance
# ==============================================================================

def test_sqli_in_team_id_path_or_injection(client, test_setup):
    """SQLi probe in path parameter: ' OR '1'='1 rejected with 422 (strict integer path)."""
    res = client.get("/api/v1/teams/'%20OR%20'1'='1/members", headers=test_setup["admin_headers"])
    assert res.status_code == 422


def test_sqli_in_team_id_path_stacked_query(client, test_setup):
    """SQLi stacked query probe: 1; DROP TABLE team; -- rejected with 422."""
    res = client.get("/api/v1/teams/1;%20DROP%20TABLE%20team;%20--/members", headers=test_setup["admin_headers"])
    assert res.status_code == 422


def test_sqli_in_team_id_path_union_select(client, test_setup):
    """SQLi UNION SELECT probe in path rejected with 422."""
    res = client.get("/api/v1/teams/1%20UNION%20SELECT%201,2,3/members", headers=test_setup["admin_headers"])
    assert res.status_code == 422


def test_sqli_in_team_id_path_hex_encoding(client, test_setup):
    """Hex-encoded SQL injection probe (0x1) in path parameter rejected with 422."""
    res = client.get("/api/v1/teams/0x1/members", headers=test_setup["admin_headers"])
    assert res.status_code == 422


def test_negative_and_zero_team_id_edge_cases(client, test_setup):
    """Boundary testing: negative (-1) and zero (0) IDs return 404 cleanly, never 500 error."""
    for bad_id in [-1, 0]:
        res_mem = client.get(f"/api/v1/teams/{bad_id}/members", headers=test_setup["admin_headers"])
        assert res_mem.status_code == 404

        res_tsk = client.get(f"/api/v1/teams/{bad_id}/tasks", headers=test_setup["admin_headers"])
        assert res_tsk.status_code == 404
