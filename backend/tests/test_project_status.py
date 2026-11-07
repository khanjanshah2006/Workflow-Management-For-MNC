"""API and service tests for US-36 project lifecycle transitions."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.features.projects.router import pm_or_admin_guard, router as project_router, update_project_status
from app.features.projects.schemas import ProjectStatusUpdate
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.enums import AuditAction, CommonStatus, PriorityLevel, ProjectStatus, UserType
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.user_account import UserAccount


class APITestClient:
    """Invoke the actual endpoint function with FastAPI-equivalent validation and guards."""

    def __init__(self, db, active_user):
        self.db = db
        self.active_user = active_user

    def put(self, url, json=None):
        class Result:
            def __init__(self, status_code, body):
                self.status_code = status_code
                self.body = body

            def json(self):
                return self.body

        try:
            project_id = int(url.split("/")[-2])
            pm_or_admin_guard(self.active_user["value"])
            payload = ProjectStatusUpdate.model_validate(json)
            result = update_project_status(
                project_id,
                payload,
                Request({"type": "http", "client": None}),
                self.db,
                self.active_user["value"],
            )
            return Result(200, result.model_dump(mode="json"))
        except ValueError as exc:
            return Result(422, {"detail": str(exc)})
        except ValidationError as exc:
            return Result(422, {"detail": exc.errors(include_url=False)})
        except HTTPException as exc:
            return Result(exc.status_code, {"detail": exc.detail})

    def close(self):
        pass


@pytest.fixture
def setup_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[UserAccount.__table__, Client.__table__, ProjectManager.__table__, Project.__table__, AuditLog.__table__],
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()

    pm_account = UserAccount(
        account_id=uuid4(), email="pm@example.test", password_hash="x", user_type=UserType.PM, is_active=True
    )
    other_pm_account = UserAccount(
        account_id=uuid4(), email="otherpm@example.test", password_hash="x", user_type=UserType.PM, is_active=True
    )
    admin = UserAccount(
        account_id=uuid4(), email="admin@example.test", password_hash="x", user_type=UserType.ADMIN, is_active=True
    )
    employee = UserAccount(
        account_id=uuid4(), email="employee@example.test", password_hash="x", user_type=UserType.EMPLOYEE, is_active=True
    )
    client_user = UserAccount(
        account_id=uuid4(), email="client@example.test", password_hash="x", user_type=UserType.CLIENT, is_active=True
    )
    db.add_all([pm_account, other_pm_account, admin, employee, client_user])
    db.flush()
    pm = ProjectManager(
        pm_id=1, account_id=pm_account.account_id, emp_code="PM-1", full_name="Assigned PM",
        email="pm@example.test", date_of_joining=date(2025, 1, 1), status=CommonStatus.ACTIVE,
    )
    other_pm = ProjectManager(
        pm_id=2, account_id=other_pm_account.account_id, emp_code="PM-2", full_name="Other PM",
        email="otherpm@example.test", date_of_joining=date(2025, 1, 1), status=CommonStatus.ACTIVE,
    )
    client = Client(
        client_id=1, company_name="Example Co", contact_person="Contact", email="contact@example.test",
        status=CommonStatus.ACTIVE,
    )
    db.add_all([pm, other_pm, client])
    db.flush()
    project = Project(
        project_id=1, client_id=1, pm_id=1, project_code="PRJ-1", name="Test project",
        start_date=date(2025, 1, 1), priority=PriorityLevel.MEDIUM, status=ProjectStatus.PLANNED,
    )
    db.add(project)
    db.commit()

    users = {
        "pm": SimpleNamespace(account_id=pm_account.account_id, user_type=UserType.PM),
        "other_pm": SimpleNamespace(account_id=other_pm_account.account_id, user_type=UserType.PM),
        "admin": SimpleNamespace(account_id=admin.account_id, user_type=UserType.ADMIN),
        "employee": SimpleNamespace(account_id=employee.account_id, user_type=UserType.EMPLOYEE),
        "client": SimpleNamespace(account_id=client_user.account_id, user_type=UserType.CLIENT),
    }
    active_user = {"value": users["pm"]}

    client_api = APITestClient(db, active_user)
    yield client_api, db, active_user, users
    client_api.close()
    db.close()
    engine.dispose()


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (ProjectStatus.PLANNED, ProjectStatus.ACTIVE),
        (ProjectStatus.PLANNED, ProjectStatus.CANCELLED),
        (ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD),
        (ProjectStatus.ACTIVE, ProjectStatus.COMPLETED),
        (ProjectStatus.ACTIVE, ProjectStatus.CANCELLED),
        (ProjectStatus.ON_HOLD, ProjectStatus.ACTIVE),
        (ProjectStatus.ON_HOLD, ProjectStatus.CANCELLED),
        (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED),
    ],
)
def test_valid_transition_persists_and_audits(setup_api, initial, target):
    client, db, _, _ = setup_api
    db.query(Project).filter_by(project_id=1).update({"status": initial})
    db.commit()

    response = client.put("/api/v1/projects/1/status", json={"status": target.value})

    assert response.status_code == 200
    assert response.json() == {"project_id": 1, "status": target.value}
    db.expire_all()
    assert db.get(Project, 1).status == target
    audit = db.query(AuditLog).filter_by(entity_name="PROJECT", entity_ref_id="1").one()
    assert audit.action == AuditAction.UPDATE
    assert json.loads(audit.old_value) == {"status": initial.value}
    assert json.loads(audit.new_value) == {"status": target.value}


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (ProjectStatus.PLANNED, ProjectStatus.PLANNED),
        (ProjectStatus.PLANNED, ProjectStatus.ON_HOLD),
        (ProjectStatus.PLANNED, ProjectStatus.COMPLETED),
        (ProjectStatus.ACTIVE, ProjectStatus.PLANNED),
        (ProjectStatus.ON_HOLD, ProjectStatus.PLANNED),
        (ProjectStatus.ON_HOLD, ProjectStatus.ON_HOLD),
        (ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED),
        (ProjectStatus.COMPLETED, ProjectStatus.PLANNED),
        (ProjectStatus.COMPLETED, ProjectStatus.ACTIVE),
        (ProjectStatus.COMPLETED, ProjectStatus.ON_HOLD),
        (ProjectStatus.COMPLETED, ProjectStatus.COMPLETED),
        (ProjectStatus.CANCELLED, ProjectStatus.PLANNED),
        (ProjectStatus.CANCELLED, ProjectStatus.ACTIVE),
        (ProjectStatus.CANCELLED, ProjectStatus.ON_HOLD),
        (ProjectStatus.CANCELLED, ProjectStatus.COMPLETED),
        (ProjectStatus.CANCELLED, ProjectStatus.CANCELLED),
    ],
)
def test_invalid_transition_returns_descriptive_400_without_audit(setup_api, initial, target):
    client, db, _, _ = setup_api
    db.query(Project).filter_by(project_id=1).update({"status": initial})
    db.commit()

    response = client.put("/api/v1/projects/1/status", json={"status": target.value})

    assert response.status_code == 400
    assert f"from {initial.value} to {target.value}" in response.json()["detail"]
    db.expire_all()
    assert db.get(Project, 1).status == initial
    assert db.query(AuditLog).count() == 0


@pytest.mark.parametrize("payload", [
    {},
    {"status": None},
    {"status": "UNKNOWN"},
    {"status": "ACTIVE; DROP TABLE project;--"},
    {"status": "ACTIVE' OR '1'='1"},
    {"status": "' OR 1=1 --"},
    {"status": ["ACTIVE"]},
    {"status": {"$ne": "PLANNED"}},
    {"status": 1},
    {"status": "ACTIVE", "status; DROP TABLE project;--": "x"},
])
def test_invalid_or_injection_status_payloads_rejected(setup_api, payload):
    client, db, _, _ = setup_api
    response = client.put("/api/v1/projects/1/status", json=payload)
    assert response.status_code == 422
    db.expire_all()
    assert db.get(Project, 1).status == ProjectStatus.PLANNED
    assert db.query(AuditLog).count() == 0


def test_sql_injection_in_project_path_is_rejected(setup_api):
    client, db, _, _ = setup_api
    response = client.put("/api/v1/projects/1%20OR%201=1/status", json={"status": "ACTIVE"})
    assert response.status_code == 422
    assert db.get(Project, 1).status == ProjectStatus.PLANNED


def test_unknown_project_returns_404(setup_api):
    client, _, _, _ = setup_api
    response = client.put("/api/v1/projects/999/status", json={"status": "ACTIVE"})
    assert response.status_code == 404


@pytest.mark.parametrize("role", ["employee", "client"])
def test_non_pm_non_admin_role_is_forbidden(setup_api, role):
    client, db, active_user, users = setup_api
    active_user["value"] = users[role]
    response = client.put("/api/v1/projects/1/status", json={"status": "ACTIVE"})
    assert response.status_code == 403
    assert db.get(Project, 1).status == ProjectStatus.PLANNED


def test_unassigned_pm_is_forbidden(setup_api):
    client, db, active_user, users = setup_api
    active_user["value"] = users["other_pm"]
    response = client.put("/api/v1/projects/1/status", json={"status": "ACTIVE"})
    assert response.status_code == 403
    assert db.get(Project, 1).status == ProjectStatus.PLANNED


def test_admin_can_transition_project(setup_api):
    client, db, active_user, users = setup_api
    active_user["value"] = users["admin"]
    response = client.put("/api/v1/projects/1/status", json={"status": "ACTIVE"})
    assert response.status_code == 200
    db.expire_all()
    assert db.get(Project, 1).status == ProjectStatus.ACTIVE


def test_assigned_pm_can_transition_project(setup_api):
    client, _, _, _ = setup_api
    response = client.put("/api/v1/projects/1/status", json={"status": "ACTIVE"})
    assert response.status_code == 200


def test_status_endpoint_is_published_in_openapi():
    app = FastAPI()
    app.include_router(project_router)
    operation = app.openapi()["paths"]["/api/v1/projects/{id}/status"]["put"]

    assert operation["summary"] == "Update project lifecycle status (US-36)"
    assert {"400", "403", "404", "422"}.issubset(operation["responses"])
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ProjectStatusUpdate"
    )
