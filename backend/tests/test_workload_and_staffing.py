"""
Unit and Integration tests for Cross-Project Employee Workload & Staffing Eligibility API (US-39).
Covers:
- Employee workload aggregation (active projects, open tasks, utilization percentage)
- Eligible employee filtering (excluding staffed on project and INACTIVE employees)
- RBAC authorization (PM and Admin access, rejection of Employee and Client)
- Project manager ownership verification
- Privacy protection (no proprietary task details exposed across PMs)
"""

from datetime import date, datetime, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.enums import (
    CommonStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    UserType,
)
from app.models.user_account import UserAccount
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.project_manager import ProjectManager
from app.models.project import Project, ProjectAssignment
from app.models.milestone import ProjectMilestone
from app.models.task import Task
from app.models.audit_log import AuditLog
from app.features.employees.schemas import EmployeeWorkloadResponse
from app.features.projects.schemas import EligibleEmployeeResponse
from app.features.employees.service import EmployeeService, EmployeeNotFoundError
from app.features.projects.service import (
    ProjectService,
    ProjectNotFoundError,
    UnauthorizedProjectAccessError,
)
from app.features.employees.router import router as employee_router
from app.features.projects.router import router as project_router


# ==============================================================================
# Fixtures & Database Setup
# ==============================================================================

@pytest.fixture
def db_session():
    """In-memory SQLite session with all required tables."""
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
            Client.__table__,
            Employee.__table__,
            ProjectManager.__table__,
            Project.__table__,
            ProjectAssignment.__table__,
            ProjectMilestone.__table__,
            Task.__table__,
            AuditLog.__table__,
        ],
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app_client(db_session):
    """FastAPI test client with database dependency override."""
    app = FastAPI()
    app.include_router(employee_router)
    app.include_router(project_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, app, db_session


@pytest.fixture
def seed_data(db_session):
    """Seed test users, project managers, departments, employees, projects, and tasks."""
    # 1. User accounts
    pm1_acc_id = uuid4()
    pm1_acc = UserAccount(
        account_id=pm1_acc_id,
        email="pm1@company.com",
        password_hash="fakehash",
        user_type=UserType.PM,
        is_active=True,
    )

    pm2_acc_id = uuid4()
    pm2_acc = UserAccount(
        account_id=pm2_acc_id,
        email="pm2@company.com",
        password_hash="fakehash",
        user_type=UserType.PM,
        is_active=True,
    )

    admin_acc_id = uuid4()
    admin_acc = UserAccount(
        account_id=admin_acc_id,
        email="admin@company.com",
        password_hash="fakehash",
        user_type=UserType.ADMIN,
        is_active=True,
    )

    emp1_acc_id = uuid4()
    emp1_acc = UserAccount(
        account_id=emp1_acc_id,
        email="emp1@company.com",
        password_hash="fakehash",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )

    client_acc_id = uuid4()
    client_acc = UserAccount(
        account_id=client_acc_id,
        email="client@clientcorp.com",
        password_hash="fakehash",
        user_type=UserType.CLIENT,
        is_active=True,
    )

    db_session.add_all([pm1_acc, pm2_acc, admin_acc, emp1_acc, client_acc])
    db_session.flush()

    # 2. PM records
    pm1 = ProjectManager(
        pm_id=1,
        account_id=pm1_acc_id,
        emp_code="PM-001",
        full_name="Alice PM",
        email="pm1@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    pm2 = ProjectManager(
        pm_id=2,
        account_id=pm2_acc_id,
        emp_code="PM-002",
        full_name="Bob PM",
        email="pm2@company.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([pm1, pm2])

    # 3. Client record
    client_rec = Client(
        client_id=1,
        account_id=client_acc_id,
        company_name="Acme Corp",
        contact_person="John Acme",
        email="client@clientcorp.com",
    )
    db_session.add(client_rec)

    # 4. Department
    eng_dept = Department(dept_id=1, name="Engineering")
    db_session.add(eng_dept)
    db_session.flush()

    # 5. Employees
    # Emp 1: Active, will have 2 active projects and 0 open tasks -> 50% utilization
    emp1 = Employee(
        emp_id=1,
        account_id=emp1_acc_id,
        dept_id=1,
        emp_code="EMP-1001",
        full_name="Charlie Dev",
        email="emp1@company.com",
        designation="Software Engineer",
        date_of_joining=date(2025, 2, 1),
        status=CommonStatus.ACTIVE,
    )

    # Emp 2: Active, 1 active project, 3 open tasks (and 1 done task) -> 25% utilization
    emp2 = Employee(
        emp_id=2,
        dept_id=1,
        emp_code="EMP-1002",
        full_name="David Tester",
        email="emp2@company.com",
        designation="QA Engineer",
        date_of_joining=date(2025, 3, 1),
        status=CommonStatus.ACTIVE,
    )

    # Emp 3: Active, 0 projects, 0 tasks -> 0% utilization
    emp3 = Employee(
        emp_id=3,
        dept_id=1,
        emp_code="EMP-1003",
        full_name="Eva Free",
        email="emp3@company.com",
        designation="DevOps Engineer",
        date_of_joining=date(2025, 4, 1),
        status=CommonStatus.ACTIVE,
    )

    # Emp 4: INACTIVE employee -> should be excluded from eligible employees
    emp4 = Employee(
        emp_id=4,
        dept_id=1,
        emp_code="EMP-1004",
        full_name="Frank Inactive",
        email="emp4@company.com",
        designation="Frontend Engineer",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.INACTIVE,
    )

    # Emp 5: Active, released from Project 1 in the past -> eligible for Project 1!
    emp5 = Employee(
        emp_id=5,
        dept_id=1,
        emp_code="EMP-1005",
        full_name="Grace Released",
        email="emp5@company.com",
        designation="Backend Engineer",
        date_of_joining=date(2025, 1, 15),
        status=CommonStatus.ACTIVE,
    )

    db_session.add_all([emp1, emp2, emp3, emp4, emp5])
    db_session.flush()

    # 6. Projects
    # Proj 1 managed by PM1
    proj1 = Project(
        project_id=1,
        client_id=1,
        pm_id=1,
        project_code="PRJ-ALPHA",
        name="Project Alpha",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
    )
    # Proj 2 managed by PM2
    proj2 = Project(
        project_id=2,
        client_id=1,
        pm_id=2,
        project_code="PRJ-BETA",
        name="Project Beta",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 11, 30),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    # Proj 3 managed by PM1
    proj3 = Project(
        project_id=3,
        client_id=1,
        pm_id=1,
        project_code="PRJ-GAMMA",
        name="Project Gamma",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 10, 31),
        priority=PriorityLevel.LOW,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add_all([proj1, proj2, proj3])
    db_session.flush()

    # 7. Project assignments
    # Emp 1 is assigned to Proj 1 and Proj 2 (active) -> 2 active projects
    asgn1 = ProjectAssignment(
        assignment_id=1,
        project_id=1,
        emp_id=1,
        role_in_project="Backend Lead",
        assigned_on=date(2026, 1, 10),
        released_on=None,
    )
    asgn2 = ProjectAssignment(
        assignment_id=2,
        project_id=2,
        emp_id=1,
        role_in_project="Architect",
        assigned_on=date(2026, 2, 15),
        released_on=None,
    )

    # Emp 2 is assigned to Proj 2 (active) -> 1 active project
    asgn3 = ProjectAssignment(
        assignment_id=3,
        project_id=2,
        emp_id=2,
        role_in_project="QA Specialist",
        assigned_on=date(2026, 2, 20),
        released_on=None,
    )

    # Emp 5 had an assignment on Proj 1, but was RELEASED -> released_on is not None
    asgn4 = ProjectAssignment(
        assignment_id=4,
        project_id=1,
        emp_id=5,
        role_in_project="Consultant",
        assigned_on=date(2026, 1, 5),
        released_on=date(2026, 1, 30),
    )

    db_session.add_all([asgn1, asgn2, asgn3, asgn4])
    db_session.flush()

    # 8. Tasks
    # Emp 1 has 0 open tasks, 1 completed task
    task1 = Task(
        task_id=1,
        project_id=1,
        assigned_to=1,
        title="PM1 Secret Task Title",
        description="Proprietary task description on Project 1",
        status=TaskStatus.DONE,
    )

    # Emp 2 has 3 open tasks (TODO, IN_PROGRESS, BLOCKED) and 1 DONE task
    task2 = Task(
        task_id=2,
        project_id=2,
        assigned_to=2,
        title="PM2 Test Task 1",
        description="Proprietary QA details on Project 2",
        status=TaskStatus.TODO,
    )
    task3 = Task(
        task_id=3,
        project_id=2,
        assigned_to=2,
        title="PM2 Test Task 2",
        description="More details",
        status=TaskStatus.IN_PROGRESS,
    )
    task4 = Task(
        task_id=4,
        project_id=2,
        assigned_to=2,
        title="PM2 Test Task 3",
        description="Blocked task",
        status=TaskStatus.BLOCKED,
    )
    task5 = Task(
        task_id=5,
        project_id=2,
        assigned_to=2,
        title="PM2 Finished Task",
        description="Finished task",
        status=TaskStatus.DONE,
    )

    db_session.add_all([task1, task2, task3, task4, task5])
    db_session.commit()

    return {
        "pm1_account": pm1_acc,
        "pm2_account": pm2_acc,
        "admin_account": admin_acc,
        "emp1_account": emp1_acc,
        "client_account": client_acc,
    }


# ==============================================================================
# 1. Schema Validation Unit Tests
# ==============================================================================

def test_employee_workload_response_schema():
    """Verify EmployeeWorkloadResponse validates correctly and supports emp_id alias."""
    workload = EmployeeWorkloadResponse(
        employee_id=5,
        active_projects_count=2,
        open_tasks_count=0,
        utilization_pct=50.0,
    )
    assert workload.employee_id == 5
    assert workload.emp_id == 5
    assert workload.active_projects_count == 2
    assert workload.open_tasks_count == 0
    assert workload.utilization_pct == 50.0

    # Also populates from emp_id dictionary
    workload_from_dict = EmployeeWorkloadResponse.model_validate({
        "emp_id": 10,
        "active_projects_count": 1,
        "open_tasks_count": 3,
        "utilization_pct": 25.0,
    })
    assert workload_from_dict.employee_id == 10
    assert workload_from_dict.emp_id == 10


def test_eligible_employee_response_schema():
    """Verify EligibleEmployeeResponse populates employee_id and nested workload."""
    resp = EligibleEmployeeResponse(
        emp_id=7,
        emp_code="EMP-1007",
        full_name="Grace Test",
        email="grace@example.com",
        designation="Software Engineer",
        active_projects_count=2,
        open_tasks_count=1,
        utilization_pct=50.0,
    )
    assert resp.emp_id == 7
    assert resp.employee_id == 7
    assert resp.active_projects_count == 2
    assert resp.workload is not None
    assert resp.workload.employee_id == 7
    assert resp.workload.active_projects_count == 2
    assert resp.workload.open_tasks_count == 1
    assert resp.workload.utilization_pct == 50.0


# ==============================================================================
# 2. Service-Layer Business Logic Unit Tests
# ==============================================================================

def test_service_get_employee_workload_emp1(db_session, seed_data):
    """
    Emp 1: 2 active projects, 0 open tasks.
    Expected: active_projects_count=2, open_tasks_count=0, utilization_pct=50.0.
    Matches exact prompt sample.
    """
    workload = EmployeeService.get_employee_workload(db=db_session, emp_id=1)
    assert workload.employee_id == 1
    assert workload.active_projects_count == 2
    assert workload.open_tasks_count == 0
    assert workload.utilization_pct == 50.0


def test_service_get_employee_workload_emp2(db_session, seed_data):
    """
    Emp 2: 1 active project, 3 open tasks (1 TODO, 1 IN_PROGRESS, 1 BLOCKED; 1 DONE excluded).
    Expected: active_projects_count=1, open_tasks_count=3, utilization_pct=25.0.
    """
    workload = EmployeeService.get_employee_workload(db=db_session, emp_id=2)
    assert workload.employee_id == 2
    assert workload.active_projects_count == 1
    assert workload.open_tasks_count == 3
    assert workload.utilization_pct == 25.0


def test_service_get_employee_workload_emp3(db_session, seed_data):
    """Emp 3: 0 active projects, 0 tasks -> 0.0% utilization."""
    workload = EmployeeService.get_employee_workload(db=db_session, emp_id=3)
    assert workload.employee_id == 3
    assert workload.active_projects_count == 0
    assert workload.open_tasks_count == 0
    assert workload.utilization_pct == 0.0


def test_service_get_employee_workload_not_found(db_session, seed_data):
    """Non-existent employee raises EmployeeNotFoundError."""
    with pytest.raises(EmployeeNotFoundError):
        EmployeeService.get_employee_workload(db=db_session, emp_id=9999)


def test_service_get_eligible_employees_for_project1(db_session, seed_data):
    """
    For Project 1:
    - Emp 1 is actively assigned -> EXCLUDED
    - Emp 4 is INACTIVE -> EXCLUDED
    - Emp 2 is eligible (assigned only to Project 2)
    - Emp 3 is eligible (unassigned)
    - Emp 5 is eligible (was on Project 1 previously, but released_on is not NULL)
    """
    eligible = ProjectService.get_eligible_employees(
        db=db_session,
        project_id=1,
        current_user=seed_data["pm1_account"],
    )
    eligible_ids = [e.emp_id for e in eligible]

    assert 1 not in eligible_ids, "Emp 1 is actively assigned to Project 1 and must be excluded"
    assert 4 not in eligible_ids, "Emp 4 is INACTIVE and must be excluded"
    assert 2 in eligible_ids, "Emp 2 is active on Project 2 only and must be eligible for Project 1"
    assert 3 in eligible_ids, "Emp 3 is unassigned and must be eligible for Project 1"
    assert 5 in eligible_ids, "Emp 5 was released from Project 1 and must be eligible again"

    # Verify workload metrics joined
    emp2_res = next(e for e in eligible if e.emp_id == 2)
    assert emp2_res.active_projects_count == 1
    assert emp2_res.open_tasks_count == 3
    assert emp2_res.utilization_pct == 25.0
    assert emp2_res.department_name == "Engineering"


def test_service_get_eligible_employees_not_found(db_session, seed_data):
    """Non-existent project raises ProjectNotFoundError."""
    with pytest.raises(ProjectNotFoundError):
        ProjectService.get_eligible_employees(
            db=db_session,
            project_id=9999,
            current_user=seed_data["pm1_account"],
        )


def test_service_get_eligible_employees_unauthorized_pm(db_session, seed_data):
    """PM2 cannot view eligible employees for Project 1 (managed by PM1)."""
    with pytest.raises(UnauthorizedProjectAccessError):
        ProjectService.get_eligible_employees(
            db=db_session,
            project_id=1,
            current_user=seed_data["pm2_account"],
        )


def test_service_get_eligible_employees_admin_allowed(db_session, seed_data):
    """Admin can view eligible employees for any project."""
    eligible = ProjectService.get_eligible_employees(
        db=db_session,
        project_id=1,
        current_user=seed_data["admin_account"],
    )
    assert len(eligible) > 0


# ==============================================================================
# 3. HTTP API Integration Tests: Workload Endpoint
# ==============================================================================

def test_api_get_workload_200_pm(app_client, seed_data):
    """GET /api/v1/employees/{id}/workload: PM retrieves workload successfully."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.get("/api/v1/employees/1/workload")
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == 1
    assert data["active_projects_count"] == 2
    assert data["open_tasks_count"] == 0
    assert data["utilization_pct"] == 50.0


def test_api_get_workload_200_admin(app_client, seed_data):
    """GET /api/v1/employees/{id}/workload: Admin retrieves workload successfully."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["admin_account"]

    response = client.get("/api/v1/employees/2/workload")
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == 2
    assert data["active_projects_count"] == 1
    assert data["open_tasks_count"] == 3
    assert data["utilization_pct"] == 25.0


def test_api_get_workload_403_employee(app_client, seed_data):
    """GET /api/v1/employees/{id}/workload: Regular Employee receives 403 Forbidden."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["emp1_account"]

    response = client.get("/api/v1/employees/1/workload")
    assert response.status_code == 403


def test_api_get_workload_403_client(app_client, seed_data):
    """GET /api/v1/employees/{id}/workload: Client receives 403 Forbidden."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["client_account"]

    response = client.get("/api/v1/employees/1/workload")
    assert response.status_code == 403


def test_api_get_workload_404_not_found(app_client, seed_data):
    """GET /api/v1/employees/{id}/workload: Non-existent employee returns 404 Not Found."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.get("/api/v1/employees/99999/workload")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==============================================================================
# 4. HTTP API Integration Tests: Eligible Employees Endpoint
# ==============================================================================

def test_api_get_eligible_employees_200_managing_pm(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: Managing PM retrieves eligible roster."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.get("/api/v1/projects/1/eligible-employees")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    emp_ids = [e["emp_id"] for e in data]
    assert 1 not in emp_ids, "Emp 1 already staffed on project 1 must be excluded"
    assert 4 not in emp_ids, "Emp 4 INACTIVE must be excluded"
    assert 2 in emp_ids
    assert 3 in emp_ids
    assert 5 in emp_ids

    # Check workload structure
    emp2_item = next(e for e in data if e["emp_id"] == 2)
    assert emp2_item["active_projects_count"] == 1
    assert emp2_item["open_tasks_count"] == 3
    assert emp2_item["utilization_pct"] == 25.0
    assert "workload" in emp2_item
    assert emp2_item["workload"]["open_tasks_count"] == 3


def test_api_get_eligible_employees_200_admin(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: Admin can view eligible employees."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["admin_account"]

    response = client.get("/api/v1/projects/1/eligible-employees")
    assert response.status_code == 200


def test_api_get_eligible_employees_403_non_managing_pm(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: Non-managing PM gets 403 Forbidden."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm2_account"]

    response = client.get("/api/v1/projects/1/eligible-employees")
    assert response.status_code == 403


def test_api_get_eligible_employees_403_regular_employee(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: Regular employee gets 403 Forbidden."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["emp1_account"]

    response = client.get("/api/v1/projects/1/eligible-employees")
    assert response.status_code == 403


def test_api_get_eligible_employees_403_client(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: Client gets 403 Forbidden."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["client_account"]

    response = client.get("/api/v1/projects/1/eligible-employees")
    assert response.status_code == 403


def test_api_get_eligible_employees_404_not_found(app_client, seed_data):
    """GET /api/v1/projects/{id}/eligible-employees: 404 when project does not exist."""
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    response = client.get("/api/v1/projects/99999/eligible-employees")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==============================================================================
# 5. Data Privacy & Leakage Verification
# ==============================================================================

def test_workload_and_eligible_apis_do_not_leak_task_or_project_details(app_client, seed_data):
    """
    Ensure PM sees aggregate statistics only without proprietary task or project details
    of other PMs' projects (US-39 Acceptance Criteria).
    """
    client, app, _ = app_client
    app.dependency_overrides[get_current_user] = lambda: seed_data["pm1_account"]

    # 1. Employee Workload endpoint
    res_workload = client.get("/api/v1/employees/2/workload")
    assert res_workload.status_code == 200
    workload_body = res_workload.text
    # Ensure proprietary task titles or descriptions never appear
    assert "PM2 Test Task" not in workload_body
    assert "Proprietary QA details" not in workload_body
    assert "Project Beta" not in workload_body

    # 2. Eligible employees endpoint
    res_eligible = client.get("/api/v1/projects/1/eligible-employees")
    assert res_eligible.status_code == 200
    eligible_body = res_eligible.text
    assert "PM2 Test Task" not in eligible_body
    assert "Proprietary QA details" not in eligible_body
    assert "Project Beta" not in eligible_body
