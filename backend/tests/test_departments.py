"""
Unit and Integration tests for Department Feature (US-05).
Covers schema validation, repository, service, API endpoints, RBAC, and audit logging.
Clearly separates real authentication tests from test-only dependency overrides.
"""

import json
import os
from uuid import uuid4

# Ensure default DATABASE_URL uses psycopg2 driver if not specified,
# preventing SQLAlchemy 2.1 from attempting to import absent psycopg (v3).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.models.department import Department
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.features.departments.dependencies import CurrentUser, get_current_user
from app.features.departments.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)
from app.features.departments.router import router as department_router


# ==============================================================================
# 1. Schema Validation Tests
# ==============================================================================

def test_department_update_description_only():
    """Omitted name should allow description-only updates."""
    payload = {"description": "Updated infrastructure engineering team"}
    update_data = DepartmentUpdate.model_validate(payload)
    assert update_data.name is None
    assert update_data.description == "Updated infrastructure engineering team"
    assert update_data.model_dump(exclude_unset=True) == {
        "description": "Updated infrastructure engineering team"
    }


def test_department_update_explicit_null_name_rejected():
    """Explicit name: null should not be treated as a valid name update."""
    payload = {"name": None, "description": "New description"}
    with pytest.raises(ValidationError) as exc_info:
        DepartmentUpdate.model_validate(payload)
    errors = exc_info.value.errors()
    assert any("Department name cannot be null" in str(e["msg"]) for e in errors)


def test_department_update_clear_description_with_null():
    """Allow clearing the optional description using description: null."""
    payload = {"description": None}
    update_data = DepartmentUpdate.model_validate(payload)
    assert update_data.description is None
    assert update_data.model_dump(exclude_unset=True) == {"description": None}


def test_department_update_clear_description_with_empty_string():
    """Allow clearing the optional description using empty string."""
    payload = {"description": "   "}
    update_data = DepartmentUpdate.model_validate(payload)
    assert update_data.description is None
    assert update_data.model_dump(exclude_unset=True) == {"description": None}


def test_department_update_empty_payload_rejected():
    """Reject a request when neither field was actually supplied."""
    payload = {}
    with pytest.raises(ValidationError) as exc_info:
        DepartmentUpdate.model_validate(payload)
    errors = exc_info.value.errors()
    assert any("At least one field" in str(e["msg"]) for e in errors)


def test_department_create_validation():
    """DepartmentCreate requires non-blank name."""
    with pytest.raises(ValidationError):
        DepartmentCreate.model_validate({"name": "   "})

    dept = DepartmentCreate.model_validate({"name": "  Engineering  ", "description": " Core "})
    assert dept.name == "Engineering"
    assert dept.description == "Core"


def test_department_response_unresolved_team_count():
    """DepartmentResponse does not return a fake default count; returns None."""
    from datetime import datetime, timezone
    dept = Department(dept_id=1, name="Eng", description="Eng", created_at=datetime.now(timezone.utc))
    resp = DepartmentResponse.model_validate(dept)
    assert resp.team_count is None


# ==============================================================================
# 2. API Endpoints, RBAC, and Audit Logging Integration Tests (In-Memory SQLite)
# ==============================================================================

@pytest.fixture
def app_and_session():
    """In-memory SQLite setup with StaticPool for clean test isolation."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Department.__table__, AuditLog.__table__],
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(department_router)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, TestingSession


def test_unauthenticated_request_missing_token_returns_401(app_and_session):
    """Real auth dependency: Missing Bearer token returns 401."""
    app, _ = app_and_session
    with TestClient(app) as client:
        response = client.get("/api/v1/departments")
        assert response.status_code == 401
        assert "missing Bearer token" in response.json()["detail"]


def test_unauthenticated_request_unintegrated_provider_returns_401(app_and_session):
    """Real auth dependency: Supplying token without central provider returns 401."""
    app, _ = app_and_session
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/departments",
            headers={"Authorization": "Bearer any_token"},
        )
        assert response.status_code == 401
        assert "Authentication provider not configured" in response.json()["detail"]


def test_insufficient_role_returns_403(app_and_session):
    """Test-only override: EMPLOYEE role is rejected with 403 on POST / PUT."""
    app, _ = app_and_session
    employee_user = CurrentUser(account_id=uuid4(), email="emp@example.com", role="EMPLOYEE")
    app.dependency_overrides[get_current_user] = lambda: employee_user

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/departments",
            json={"name": "Finance", "description": "Accounting"},
        )
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        response_put = client.put(
            "/api/v1/departments/1",
            json={"description": "Accounting Update"},
        )
        assert response_put.status_code == 403


def test_create_department_success_201_and_audit(app_and_session):
    """Test-only override: HR_MANAGER creates department (201) and logs audit."""
    app, TestingSession = app_and_session
    hr_actor_id = uuid4()
    hr_user = CurrentUser(account_id=hr_actor_id, email="hr@example.com", role="HR_MANAGER")
    app.dependency_overrides[get_current_user] = lambda: hr_user

    with TestClient(app) as client:
        payload = {"name": "Engineering", "description": "Core product engineering"}
        response = client.post("/api/v1/departments", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["dept_id"] is not None
        assert data["name"] == "Engineering"
        assert data["description"] == "Core product engineering"
        assert data["team_count"] is None  # Unresolved requirement returns None, not fake 0

    # Verify audit log in SQLite test database
    db = TestingSession()
    audit = db.query(AuditLog).filter(
        AuditLog.entity_name == "DEPARTMENT",
        AuditLog.action == AuditAction.CREATE,
        AuditLog.entity_ref_id == str(data["dept_id"]),
    ).first()
    assert audit is not None
    assert audit.account_id == hr_actor_id
    assert json.loads(audit.new_value)["name"] == "Engineering"
    db.close()


def test_create_department_duplicate_name_409(app_and_session):
    """Duplicate department name returns 409 Conflict."""
    app, _ = app_and_session
    hr_user = CurrentUser(account_id=uuid4(), email="hr@example.com", role="HR_MANAGER")
    app.dependency_overrides[get_current_user] = lambda: hr_user

    with TestClient(app) as client:
        client.post("/api/v1/departments", json={"name": "Marketing"})
        response = client.post("/api/v1/departments", json={"name": "marketing"})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


def test_list_departments_pagination_200(app_and_session):
    """GET /api/v1/departments returns paginated list and X-Total-Count header."""
    app, _ = app_and_session
    hr_user = CurrentUser(account_id=uuid4(), email="hr@example.com", role="HR_MANAGER")
    emp_user = CurrentUser(account_id=uuid4(), email="emp@example.com", role="EMPLOYEE")

    # Seed 3 departments as HR
    app.dependency_overrides[get_current_user] = lambda: hr_user
    with TestClient(app) as client:
        client.post("/api/v1/departments", json={"name": "Dept A"})
        client.post("/api/v1/departments", json={"name": "Dept B"})
        client.post("/api/v1/departments", json={"name": "Dept C"})

    # Employee can read
    app.dependency_overrides[get_current_user] = lambda: emp_user
    with TestClient(app) as client:
        response = client.get("/api/v1/departments?skip=0&limit=2")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert response.headers["X-Total-Count"] == "3"


def test_get_department_by_id_200_and_404(app_and_session):
    """GET /api/v1/departments/{id} returns 200 if found and 404 if missing."""
    app, _ = app_and_session
    hr_user = CurrentUser(account_id=uuid4(), email="hr@example.com", role="HR_MANAGER")
    emp_user = CurrentUser(account_id=uuid4(), email="emp@example.com", role="EMPLOYEE")

    app.dependency_overrides[get_current_user] = lambda: hr_user
    with TestClient(app) as client:
        created = client.post("/api/v1/departments", json={"name": "Sales"}).json()
        dept_id = created["dept_id"]

    app.dependency_overrides[get_current_user] = lambda: emp_user
    with TestClient(app) as client:
        res_ok = client.get(f"/api/v1/departments/{dept_id}")
        assert res_ok.status_code == 200
        assert res_ok.json()["name"] == "Sales"

        res_missing = client.get("/api/v1/departments/99999")
        assert res_missing.status_code == 404
        assert "not found" in res_missing.json()["detail"].lower()


def test_update_department_success_200_and_audit(app_and_session):
    """ADMIN role can update department with audit logging."""
    app, TestingSession = app_and_session
    admin_actor_id = uuid4()
    admin_user = CurrentUser(account_id=admin_actor_id, email="admin@example.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(app) as client:
        created = client.post("/api/v1/departments", json={"name": "Design", "description": "UI/UX"}).json()
        dept_id = created["dept_id"]

        upd_res = client.put(
            f"/api/v1/departments/{dept_id}",
            json={"description": "Product Design & Research"},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["description"] == "Product Design & Research"
        assert upd_res.json()["name"] == "Design"

    # Verify audit log in SQLite test database
    db = TestingSession()
    audit = db.query(AuditLog).filter(
        AuditLog.entity_name == "DEPARTMENT",
        AuditLog.action == AuditAction.UPDATE,
        AuditLog.entity_ref_id == str(dept_id),
    ).first()
    assert audit is not None
    assert audit.account_id == admin_actor_id
    assert json.loads(audit.old_value)["description"] == "UI/UX"
    assert json.loads(audit.new_value)["description"] == "Product Design & Research"
    db.close()


def test_update_department_duplicate_name_409(app_and_session):
    """Renaming a department to an existing name returns 409 Conflict."""
    app, _ = app_and_session
    hr_user = CurrentUser(account_id=uuid4(), email="hr@example.com", role="HR_MANAGER")
    app.dependency_overrides[get_current_user] = lambda: hr_user

    with TestClient(app) as client:
        client.post("/api/v1/departments", json={"name": "Legal"})
        dept2 = client.post("/api/v1/departments", json={"name": "Compliance"}).json()

        res = client.put(
            f"/api/v1/departments/{dept2['dept_id']}",
            json={"name": "Legal"},
        )
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]


def test_update_department_missing_404(app_and_session):
    """Updating a non-existent department returns 404 Not Found."""
    app, _ = app_and_session
    hr_user = CurrentUser(account_id=uuid4(), email="hr@example.com", role="HR_MANAGER")
    app.dependency_overrides[get_current_user] = lambda: hr_user

    with TestClient(app) as client:
        res = client.put(
            "/api/v1/departments/99999",
            json={"name": "New Name"},
        )
        assert res.status_code == 404


def test_delete_endpoint_not_exposed(app_and_session):
    """DELETE endpoint is strictly not exposed on /api/v1/departments/{dept_id}."""
    app, _ = app_and_session
    admin_user = CurrentUser(account_id=uuid4(), email="admin@example.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(app) as client:
        res = client.delete("/api/v1/departments/1")
        assert res.status_code in (404, 405)
