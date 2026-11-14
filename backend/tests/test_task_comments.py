"""Integration coverage for task comment threads and their access boundaries."""

from datetime import date
import uuid
from urllib.parse import unquote

import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rbac import require_role
from app.db.base import Base
from app.features.tasks.router import create_task_comment, get_task_comments, router as tasks_router
from app.features.tasks.schemas import TaskCommentCreate
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import CommonStatus, PriorityLevel, ProjectStatus, TaskStatus, TeamStatus, UserType
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task, TaskComment
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


class APITestClient:
    """Call the registered route functions with FastAPI-style validation and role checks."""

    def __init__(self, db, actor):
        self.db = db
        self.actor = actor

    class Result:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self.body = body

        def json(self):
            return self.body

    def _route(self, method, url, payload=None):
        try:
            raw_id = unquote(url.split("/")[-2])
            task_id = int(raw_id)
            user = self.actor["user"]
            require_role(user, allowed=["EMPLOYEE", "PM", "ADMIN", "SYSTEM_ADMIN"])
            if method == "POST":
                body = TaskCommentCreate.model_validate(payload)
                result = create_task_comment(task_id, body, user, self.db)
                return self.Result(201, result.model_dump(mode="json"))
            result = get_task_comments(task_id, user, self.db)
            return self.Result(200, [item.model_dump(mode="json") for item in result])
        except (ValueError, ValidationError) as exc:
            return self.Result(422, {"detail": str(exc)})
        except HTTPException as exc:
            return self.Result(exc.status_code, {"detail": exc.detail})

    def post(self, url, json=None):
        return self._route("POST", url, json)

    def get(self, url):
        return self._route("GET", url)


@pytest.fixture
def setup_comments():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    department = Department(dept_id=1, name="Engineering")
    accounts = {
        role: UserAccount(account_id=uuid.uuid4(), email=f"{role.lower()}@example.test", password_hash="x", user_type=role, is_active=True)
        for role in [UserType.EMPLOYEE, UserType.PM, UserType.ADMIN, UserType.SYSTEM_ADMIN, UserType.CLIENT]
    }
    accounts["lead"] = UserAccount(account_id=uuid.uuid4(), email="lead@example.test", password_hash="x", user_type=UserType.EMPLOYEE, is_active=True)
    accounts["member"] = UserAccount(account_id=uuid.uuid4(), email="member@example.test", password_hash="x", user_type=UserType.EMPLOYEE, is_active=True)
    accounts["outsider"] = UserAccount(account_id=uuid.uuid4(), email="outsider@example.test", password_hash="x", user_type=UserType.EMPLOYEE, is_active=True)
    client_row = Client(client_id=1, company_name="Acme", contact_person="Contact", email="client@acme.test", status=CommonStatus.ACTIVE)
    pm = ProjectManager(pm_id=1, account_id=accounts[UserType.PM].account_id, dept_id=1, emp_code="PM-1", full_name="Priya Manager", email=accounts[UserType.PM].email, date_of_joining=date(2020, 1, 1), status=CommonStatus.ACTIVE)
    db.add_all([department, *accounts.values(), client_row, pm])
    db.flush()
    employees = {
        key: Employee(emp_id=idx, account_id=accounts[key].account_id, dept_id=1, emp_code=f"EMP-{idx}", full_name=name, email=accounts[key].email, designation="Engineer", date_of_joining=date(2021, 1, 1), status=CommonStatus.ACTIVE)
        for key, idx, name in [(UserType.EMPLOYEE, 1, "Asha Assignee"), ("lead", 2, "Liam Team Lead"), ("member", 3, "Mina Member"), ("outsider", 4, "Owen Outsider")]
    }
    project = Project(project_id=1, client_id=1, pm_id=1, project_code="PRJ-1", name="Project One", start_date=date(2025, 1, 1), priority=PriorityLevel.MEDIUM, status=ProjectStatus.ACTIVE)
    db.add_all([*employees.values(), project])
    db.flush()
    team = Team(team_id=1, project_id=1, lead_emp_id=employees["lead"].emp_id, name="Core", status=TeamStatus.ACTIVE)
    task = Task(task_id=1, project_id=1, team_id=team.team_id, assigned_to=employees[UserType.EMPLOYEE].emp_id, created_by=employees["lead"].emp_id, title="Build feature", status=TaskStatus.TODO)
    db.add_all([team, task])
    db.flush()
    db.add_all([TeamMember(team_id=1, emp_id=employees[UserType.EMPLOYEE].emp_id), TeamMember(team_id=1, emp_id=employees["lead"].emp_id), TeamMember(team_id=1, emp_id=employees["member"].emp_id)])
    db.commit()

    actor = {"user": accounts[UserType.EMPLOYEE]}
    test_client = APITestClient(db, actor)
    yield test_client, db, actor, accounts, employees
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_assignee_can_post_and_comment_is_persisted(setup_comments):
    client, db, _, _, employees = setup_comments
    response = client.post("/api/v1/tasks/1/comments", json={"content": "Ready for review"})
    assert response.status_code == 201
    assert response.json()["content"] == "Ready for review"
    assert response.json()["author_name"] == employees[UserType.EMPLOYEE].full_name
    assert response.json()["author_role"] == "EMPLOYEE"
    assert db.query(TaskComment).count() == 1


def test_assignee_comment_notifies_team_lead(setup_comments):
    client, db, _, accounts, _ = setup_comments
    assert client.post("/api/v1/tasks/1/comments", json={"content": "Update"}).status_code == 201
    notification = db.query(Notification).one()
    assert notification.account_id == accounts["lead"].account_id
    assert notification.type == "TASK_COMMENT"
    assert "/tasks/1" == notification.link


def test_team_lead_can_comment_and_notifies_assignee(setup_comments):
    client, db, actor, accounts, _ = setup_comments
    actor["user"] = accounts["lead"]
    response = client.post("/api/v1/tasks/1/comments", json={"content": "Please add tests"})
    assert response.status_code == 201
    assert response.json()["author_role"] == "TEAM_LEAD"
    assert db.query(Notification).one().account_id == accounts[UserType.EMPLOYEE].account_id


def test_project_pm_can_comment_and_notifies_assignee(setup_comments):
    client, db, actor, accounts, _ = setup_comments
    actor["user"] = accounts[UserType.PM]
    response = client.post("/api/v1/tasks/1/comments", json={"content": "Project update"})
    assert response.status_code == 201
    assert response.json()["author_name"] == "Priya Manager"
    assert response.json()["author_role"] == "PM"
    assert db.query(Notification).one().account_id == accounts[UserType.EMPLOYEE].account_id


@pytest.mark.parametrize("role", [UserType.ADMIN, UserType.SYSTEM_ADMIN])
def test_admin_roles_can_comment(setup_comments, role):
    client, _, actor, accounts, _ = setup_comments
    actor["user"] = accounts[role]
    assert client.post("/api/v1/tasks/1/comments", json={"content": "Admin note"}).status_code == 201


def test_project_team_member_can_comment(setup_comments):
    client, db, actor, accounts, _ = setup_comments
    actor["user"] = accounts["member"]
    assert client.post("/api/v1/tasks/1/comments", json={"content": "Team note"}).status_code == 201
    assert db.query(Notification).one().account_id == accounts[UserType.EMPLOYEE].account_id


@pytest.mark.parametrize("method", ["get", "post"])
def test_external_client_is_forbidden(setup_comments, method):
    client, _, actor, accounts, _ = setup_comments
    actor["user"] = accounts[UserType.CLIENT]
    response = getattr(client, method)("/api/v1/tasks/1/comments", json={"content": "Hello"}) if method == "post" else getattr(client, method)("/api/v1/tasks/1/comments")
    assert response.status_code == 403


@pytest.mark.parametrize("method", ["get", "post"])
def test_non_team_member_is_forbidden(setup_comments, method):
    client, _, actor, accounts, _ = setup_comments
    actor["user"] = accounts["outsider"]
    response = getattr(client, method)("/api/v1/tasks/1/comments", json={"content": "Hello"}) if method == "post" else getattr(client, method)("/api/v1/tasks/1/comments")
    assert response.status_code == 403


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_task_returns_404(setup_comments, method):
    client, _, _, _, _ = setup_comments
    response = client.post("/api/v1/tasks/999/comments", json={"content": "Hello"}) if method == "post" else client.get("/api/v1/tasks/999/comments")
    assert response.status_code == 404


@pytest.mark.parametrize("payload", [
    {}, {"content": ""}, {"content": "   "}, {"content": "x" * 2001},
    {"content": None}, {"content": 7}, {"content": ["hello"]},
    {"content": "hello", "author_emp_id": 1}, {"content": "hello", "task_id": 2},
    {"content": "hello", "role": "ADMIN"},
])
def test_invalid_or_unexpected_payload_rejected(setup_comments, payload):
    client, db, _, _, _ = setup_comments
    response = client.post("/api/v1/tasks/1/comments", json=payload)
    assert response.status_code == 422
    assert db.query(TaskComment).count() == 0
    assert db.query(Notification).count() == 0


@pytest.mark.parametrize("content", ["x", "x" * 2000])
def test_content_length_boundaries_are_accepted(setup_comments, content):
    client, _, _, _, _ = setup_comments
    response = client.post("/api/v1/tasks/1/comments", json={"content": content})
    assert response.status_code == 201
    assert response.json()["content"] == content


@pytest.mark.parametrize("payload", [
    "' OR '1'='1", "x'); DROP TABLE task_comment;--", "<script>alert(1)</script>",
    "${jndi:ldap://example.test/a}", "../../../../etc/passwd",
])
def test_injection_and_markup_payloads_are_stored_as_plain_text(setup_comments, payload):
    client, db, _, _, _ = setup_comments
    response = client.post("/api/v1/tasks/1/comments", json={"content": payload})
    assert response.status_code == 201
    assert db.query(TaskComment).one().content == payload
    assert db.query(Task).filter_by(task_id=1).count() == 1


def test_comments_are_returned_chronologically_with_author_metadata(setup_comments):
    client, db, actor, accounts, employees = setup_comments
    client.post("/api/v1/tasks/1/comments", json={"content": "First"})
    actor["user"] = accounts["lead"]
    client.post("/api/v1/tasks/1/comments", json={"content": "Second"})
    response = client.get("/api/v1/tasks/1/comments")
    assert response.status_code == 200
    assert [item["content"] for item in response.json()] == ["First", "Second"]
    assert response.json()[0]["author_name"] == employees[UserType.EMPLOYEE].full_name
    assert response.json()[1]["author_name"] == employees["lead"].full_name
    assert response.json()[0]["created_at"] <= response.json()[1]["created_at"]


def test_empty_thread_returns_empty_list(setup_comments):
    client, _, _, _, _ = setup_comments
    assert client.get("/api/v1/tasks/1/comments").json() == []


def test_sql_injection_in_task_path_is_rejected_without_mutation(setup_comments):
    client, db, _, _, _ = setup_comments
    response = client.post("/api/v1/tasks/1%20OR%201=1/comments", json={"content": "Attack"})
    assert response.status_code == 422
    assert db.query(TaskComment).count() == 0


def test_comment_notification_does_not_notify_author(setup_comments):
    client, db, actor, accounts, _ = setup_comments
    actor["user"] = accounts["lead"]
    assert client.post("/api/v1/tasks/1/comments", json={"content": "Note"}).status_code == 201
    assert all(notification.account_id != accounts["lead"].account_id for notification in db.query(Notification).all())


def test_invalid_path_id_has_no_database_side_effect(setup_comments):
    client, db, _, _, _ = setup_comments
    assert client.post("/api/v1/tasks/not-an-int/comments", json={"content": "Note"}).status_code == 422
    assert db.query(TaskComment).count() == 0


def test_comment_routes_are_published_in_openapi():
    api = FastAPI()
    api.include_router(tasks_router)
    paths = api.openapi()["paths"]
    assert paths["/api/v1/tasks/{id}/comments"]["post"]["responses"]["201"]
    assert paths["/api/v1/tasks/{id}/comments"]["get"]["responses"]["200"]
