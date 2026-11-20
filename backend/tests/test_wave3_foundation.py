import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core import scope
from app.db.base import Base
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import AuditAction, ProjectStatus, ReportFormat, TeamStatus, UserType
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.system_parameter import SystemParameter
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount
from scripts.seed_wave3_demo import seed_wave3_demo


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _account(db, user_type=UserType.EMPLOYEE):
    acc = UserAccount(
        account_id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@x.com",
        password_hash="x", user_type=user_type,
    )
    db.add(acc)
    db.flush()
    return acc


def _employee(db, name):
    acc = _account(db)
    emp = Employee(
        account_id=acc.account_id, emp_code=name, full_name=name, email=f"{name}@x.com",
        designation="Dev", date_of_joining=date(2024, 1, 1),
    )
    db.add(emp)
    db.flush()
    return emp


def _pm(db, name):
    acc = _account(db, UserType.PM)
    pm = ProjectManager(
        account_id=acc.account_id, emp_code=name, full_name=name, email=f"{name}@x.com",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(pm)
    db.flush()
    return pm


def _project(db, pm, client, code, status=ProjectStatus.ACTIVE):
    project = Project(
        client_id=client.client_id, pm_id=pm.pm_id, project_code=code, name=code,
        start_date=date(2026, 1, 1), status=status,
    )
    db.add(project)
    db.flush()
    return project


def test_scope_helpers_team_lead_membership(db):
    lead, member, outsider = (_employee(db, n) for n in ("lead", "member", "outsider"))
    active = Team(name="Active", lead_emp_id=lead.emp_id, status=TeamStatus.ACTIVE)
    disbanded = Team(name="Old", lead_emp_id=lead.emp_id, status=TeamStatus.DISBANDED)
    db.add_all([active, disbanded])
    db.flush()
    db.add_all([
        TeamMember(team_id=active.team_id, emp_id=member.emp_id),
        TeamMember(team_id=disbanded.team_id, emp_id=outsider.emp_id),
    ])
    db.flush()

    assert scope.led_team_ids(db, lead.emp_id) == {active.team_id}
    assert scope.employee_team_ids(db, member.emp_id) == {active.team_id}
    assert scope.employee_team_ids(db, outsider.emp_id) == set()
    assert scope.is_team_lead_of(db, lead.emp_id, member.emp_id) is True
    assert scope.is_team_lead_of(db, lead.emp_id, outsider.emp_id) is False
    assert scope.team_lead_account_ids_for(db, member.emp_id) == [lead.account_id]
    assert scope.team_lead_account_ids_for(db, outsider.emp_id) == []

    lead_user = db.get(UserAccount, lead.account_id)
    assert scope.resolve_employee(db, lead_user).emp_id == lead.emp_id
    assert scope.resolve_pm(db, lead_user) is None


def test_team_lead_account_ids_excludes_the_employee_themself(db):
    lead = _employee(db, "lead")
    team = Team(name="T", lead_emp_id=lead.emp_id, status=TeamStatus.ACTIVE)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.team_id, emp_id=lead.emp_id))
    db.flush()

    assert scope.team_lead_account_ids_for(db, lead.emp_id) == []


def test_scope_helpers_staffing_pms_excludes_released_assignments(db):
    emp = _employee(db, "emp")
    client = Client(company_name="C", contact_person="C", email="c@x.com")
    db.add(client)
    db.flush()
    pm_active, pm_released, pm_cancelled = (_pm(db, n) for n in ("pm1", "pm2", "pm3"))
    p_active = _project(db, pm_active, client, "P1")
    p_released = _project(db, pm_released, client, "P2")
    p_cancelled = _project(db, pm_cancelled, client, "P3", status=ProjectStatus.CANCELLED)
    db.add_all([
        ProjectAssignment(project_id=p_active.project_id, emp_id=emp.emp_id, role_in_project="Dev",
                          assigned_on=date(2026, 1, 1)),
        ProjectAssignment(project_id=p_released.project_id, emp_id=emp.emp_id, role_in_project="Dev",
                          assigned_on=date(2026, 1, 1), released_on=date(2026, 2, 1)),
        ProjectAssignment(project_id=p_cancelled.project_id, emp_id=emp.emp_id, role_in_project="Dev",
                          assigned_on=date(2026, 1, 1)),
    ])
    db.flush()

    assert scope.staffing_pm_account_ids_for(db, emp.emp_id) == [pm_active.account_id]
    assert [p.project_id for p in scope.staffing_projects_for(db, emp.emp_id)] == [p_active.project_id]
    assert scope.pm_manages_project(db, pm_active.pm_id, p_active.project_id) is True
    assert scope.pm_manages_project(db, pm_released.pm_id, p_active.project_id) is False


def test_get_int_param_reads_value_and_falls_back(db):
    db.add_all([
        SystemParameter(key="GOOD", value="7", value_type="integer"),
        SystemParameter(key="BAD", value="seven", value_type="integer"),
    ])
    db.flush()

    assert scope.get_int_param(db, "GOOD", 2) == 7
    assert scope.get_int_param(db, "BAD", 2) == 2
    assert scope.get_int_param(db, "MISSING", 5) == 5


def test_new_enum_values_present():
    assert UserType.MNC_EXECUTIVE.value == "MNC_EXECUTIVE"
    assert AuditAction.EXPORT.value == "EXPORT"
    assert {f.value for f in ReportFormat} == {"PDF", "CSV"}


def test_leave_and_executive_routers_registered():
    # The routers are empty until the Wave 3 feature issues add endpoints, so check wiring, not paths.
    from app import main
    from app.features.executive import executive_router
    from app.features.leave import leave_router

    assert main.leave_router is leave_router
    assert main.executive_router is executive_router
    assert leave_router.prefix == "/api/v1/leave"
    assert executive_router.prefix == "/api/v1/executive"


def test_seed_wave3_demo_is_idempotent(db):
    today = date(2026, 11, 18)

    def counts():
        return {
            table.name: db.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }

    seed_wave3_demo(db, today=today, password="Seed@123")
    first = counts()
    seed_wave3_demo(db, today=today, password="Seed@123")
    second = counts()

    assert first == second
    # A later run moves the relative dates instead of creating new rows.
    seed_wave3_demo(db, today=date(2026, 11, 25), password="Seed@123")
    assert counts() == first
    assert first["user_account"] == 9
    assert first["task"] == 10
    assert first["leave_request"] == 3
    assert first["audit_log"] == 3
    emails = set(db.scalars(select(UserAccount.email)))
    assert {"john.teamlead@company.com", "executive@company.com", "client@acme.com"} <= emails
