"""Review queue and leave decision API coverage for S4-BE-4."""
from datetime import date
import json
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.features.leave.review_router import (
    approve_leave_request,
    get_pending_leave_requests,
    reject_leave_request,
)
from app.features.leave.schemas import LeaveApprovalPayload, LeaveRejectionPayload
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    LeaveStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.notification import Notification
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


class DirectLeaveApiClient:
    """Invoke registered endpoint functions with FastAPI/Pydantic request validation."""

    class Result:
        def __init__(self, status_code: int, body):
            self.status_code = status_code
            self._body = body

        def json(self):
            return self._body

    def __init__(self, db, actor):
        self.db = db
        self.actor = actor

    def _result(self, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if hasattr(result, "model_dump"):
                body = result.model_dump(mode="json")
            else:
                body = result
            return self.Result(200, body)
        except (ValueError, ValidationError) as exc:
            return self.Result(422, {"detail": str(exc)})
        except HTTPException as exc:
            return self.Result(exc.status_code, {"detail": exc.detail})

    def get(self, url: str):
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        try:
            page = int(query.get("page", ["1"])[0])
            limit = int(query.get("limit", ["20"])[0])
            if page < 1 or limit < 1 or limit > 100:
                raise ValueError("page and limit are outside their allowed range")
        except ValueError as exc:
            return self.Result(422, {"detail": str(exc)})
        status_filter = query.get("status", ["PENDING"])[0]
        return self._result(
            get_pending_leave_requests,
            status_filter,
            page,
            limit,
            self.db,
            self.actor["user"],
        )

    def put(self, url: str, json=None):
        parts = urlsplit(url).path.strip("/").split("/")
        try:
            leave_id = int(parts[-2])
        except (ValueError, IndexError):
            return self.Result(422, {"detail": "leave id must be an integer"})
        if parts[-1] == "approve":
            try:
                payload = LeaveApprovalPayload.model_validate(json or {})
            except ValidationError as exc:
                return self.Result(422, {"detail": exc.errors()})
            return self._result(
                approve_leave_request,
                leave_id,
                payload,
                self.db,
                self.actor["user"],
            )
        try:
            payload = LeaveRejectionPayload.model_validate(json)
        except ValidationError as exc:
            return self.Result(422, {"detail": exc.errors()})
        return self._result(
            reject_leave_request,
            leave_id,
            payload,
            self.db,
            self.actor["user"],
        )


@pytest.fixture
def leave_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    department = Department(dept_id=1, name="Engineering")

    def user(key: str, role: UserType) -> UserAccount:
        return UserAccount(
            account_id=uuid.uuid4(),
            email=f"{key}@example.test",
            password_hash="test-hash",
            user_type=role,
            is_active=True,
        )

    users = {
        "applicant": user("applicant", UserType.EMPLOYEE),
        "other": user("other", UserType.EMPLOYEE),
        "lead": user("lead", UserType.TEAM_LEAD),
        "other_lead": user("other-lead", UserType.TEAM_LEAD),
        "hr": user("hr", UserType.HR),
        "admin": user("admin", UserType.ADMIN),
        "pm": user("pm", UserType.PM),
        "employee": user("plain-employee", UserType.EMPLOYEE),
    }
    client_row = Client(
        client_id=1,
        company_name="Acme",
        contact_person="Contact",
        email="contact@acme.test",
        status=CommonStatus.ACTIVE,
    )
    pm = ProjectManager(
        pm_id=1,
        account_id=users["pm"].account_id,
        dept_id=1,
        emp_code="PM-1",
        full_name="Pat Manager",
        email=users["pm"].email,
        date_of_joining=date(2020, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add_all([department, *users.values(), client_row, pm])
    db.flush()

    def employee(key: str, emp_id: int, name: str) -> Employee:
        return Employee(
            emp_id=emp_id,
            account_id=users[key].account_id,
            dept_id=1,
            emp_code=f"EMP-{emp_id}",
            full_name=name,
            email=users[key].email,
            designation="Engineer",
            date_of_joining=date(2021, 1, 1),
            status=CommonStatus.ACTIVE,
        )

    employees = {
        "applicant": employee("applicant", 1, "Ari Applicant"),
        "other": employee("other", 2, "Ollie Other"),
        "lead": employee("lead", 3, "Terry Team Lead"),
        "other_lead": employee("other_lead", 4, "Lee Other Lead"),
        "employee": employee("employee", 5, "Evan Employee"),
    }
    project = Project(
        project_id=1,
        client_id=1,
        pm_id=1,
        project_code="PRJ-1",
        name="Release Project",
        start_date=date(2026, 1, 1),
        priority=PriorityLevel.MEDIUM,
        status=ProjectStatus.ACTIVE,
    )
    db.add_all([*employees.values(), project])
    db.flush()
    teams = {
        "lead": Team(team_id=1, project_id=1, lead_emp_id=3, name="Team A", status=TeamStatus.ACTIVE),
        "other_lead": Team(team_id=2, project_id=1, lead_emp_id=4, name="Team B", status=TeamStatus.ACTIVE),
    }
    db.add_all(teams.values())
    db.flush()
    db.add_all(
        [
            TeamMember(team_id=1, emp_id=1),
            TeamMember(team_id=1, emp_id=3),
            TeamMember(team_id=2, emp_id=2),
        ]
    )
    leave_type = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True)
    db.add(leave_type)
    db.flush()
    db.add(ProjectAssignment(project_id=1, emp_id=1, role_in_project="Engineer", assigned_on=date(2026, 1, 1)))
    db.add_all(
        [
            Task(
                project_id=1,
                team_id=1,
                assigned_to=1,
                title="Release review",
                status=TaskStatus.IN_PROGRESS,
                start_date=date(2026, 12, 7),
                due_date=date(2026, 12, 8),
            ),
            Task(
                project_id=1,
                team_id=1,
                assigned_to=1,
                title="Already complete",
                status=TaskStatus.DONE,
                due_date=date(2026, 12, 8),
            ),
        ]
    )
    db.commit()

    actor = {"user": users["lead"]}
    client = DirectLeaveApiClient(db, actor)
    yield client, db, actor, users, employees, leave_type
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def add_request(db, leave_type, emp_id=1, start=date(2026, 12, 7), end=date(2026, 12, 9), days=3, status=LeaveStatus.PENDING):
    request = LeaveRequest(
        emp_id=emp_id,
        leave_type_id=leave_type.leave_type_id,
        start_date=start,
        end_date=end,
        total_days=days,
        reason="Family event and travel.",
        status=status,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def test_pending_queue_scoped_to_led_teams(leave_api):
    client, db, _, _, _, leave_type = leave_api
    own = add_request(db, leave_type, emp_id=3)
    visible = add_request(db, leave_type, emp_id=1, start=date(2026, 12, 10), end=date(2026, 12, 10), days=1)
    hidden = add_request(db, leave_type, emp_id=2)

    response = client.get("/api/v1/leave/requests/pending")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["leave_id"] for item in body["items"]] == [visible.leave_id]
    assert own.leave_id not in [item["leave_id"] for item in body["items"]]
    assert hidden.leave_id not in [item["leave_id"] for item in body["items"]]
    assert body["items"][0]["employee_name"] == "Ari Applicant"
    assert body["items"][0]["leave_type_name"] == "Annual Leave"


@pytest.mark.parametrize("role_key", ["hr", "admin"])
def test_hr_and_admin_pending_queue_lists_all_requests(leave_api, role_key):
    client, db, actor, users, _, leave_type = leave_api
    first = add_request(db, leave_type, emp_id=1)
    second = add_request(db, leave_type, emp_id=2)
    actor["user"] = users[role_key]

    response = client.get("/api/v1/leave/requests/pending")

    assert response.status_code == 200
    assert {item["leave_id"] for item in response.json()["items"]} == {first.leave_id, second.leave_id}


def test_pending_queue_filter_all_status_and_ordering(leave_api):
    client, db, actor, users, _, leave_type = leave_api
    later = add_request(db, leave_type, emp_id=1, start=date(2026, 12, 14), end=date(2026, 12, 14), days=1)
    earlier = add_request(db, leave_type, emp_id=1, start=date(2026, 12, 7), end=date(2026, 12, 7), days=1)
    done = add_request(db, leave_type, emp_id=2, status=LeaveStatus.REJECTED)
    actor["user"] = users["hr"]

    pending = client.get("/api/v1/leave/requests/pending?status=PENDING")
    all_statuses = client.get("/api/v1/leave/requests/pending?status=ALL")

    assert pending.status_code == 200
    assert [item["leave_id"] for item in pending.json()["items"]] == [earlier.leave_id, later.leave_id]
    assert all_statuses.status_code == 200
    assert {item["leave_id"] for item in all_statuses.json()["items"]} == {earlier.leave_id, later.leave_id, done.leave_id}


def test_pending_queue_pagination_validates_limits(leave_api):
    client, db, _, _, _, leave_type = leave_api
    add_request(db, leave_type, start=date(2026, 12, 7), end=date(2026, 12, 7), days=1)
    add_request(db, leave_type, start=date(2026, 12, 8), end=date(2026, 12, 8), days=1)

    page = client.get("/api/v1/leave/requests/pending?page=2&limit=1")
    invalid_page = client.get("/api/v1/leave/requests/pending?page=0")
    invalid_limit = client.get("/api/v1/leave/requests/pending?limit=101")

    assert page.status_code == 200
    assert page.json()["page"] == 2 and page.json()["limit"] == 1
    assert len(page.json()["items"]) == 1
    assert invalid_page.status_code == invalid_limit.status_code == 422


def test_pending_queue_counts_conflicting_tasks_in_one_item_field(leave_api):
    client, db, _, _, _, leave_type = leave_api
    request = add_request(db, leave_type)

    response = client.get("/api/v1/leave/requests/pending")

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["leave_id"] == request.leave_id)
    assert item["conflicting_task_count"] == 1


def test_tl_approve_pending_leave_notifies_employee_and_staffing_pms(leave_api):
    client, db, _, users, _, leave_type = leave_api
    request = add_request(db, leave_type)

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={"review_remarks": "Coverage arranged."})

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["reviewed_by_account_id"] == str(users["lead"].account_id)
    assert response.json()["review_remarks"] == "Coverage arranged."
    notifications = db.query(Notification).all()
    assert {(item.account_id, item.type) for item in notifications} == {
        (users["applicant"].account_id, "LEAVE_APPROVED"),
        (users["pm"].account_id, "STAFF_LEAVE_APPROVED"),
    }
    assert response.json()["reviewed_at"] is not None


def test_hr_approval_also_notifies_applicant_team_lead(leave_api):
    client, db, actor, users, _, leave_type = leave_api
    request = add_request(db, leave_type)
    actor["user"] = users["hr"]

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={})

    assert response.status_code == 200
    assert response.json()["review_remarks"] is None
    recipients = {(item.account_id, item.type) for item in db.query(Notification).all()}
    assert (users["applicant"].account_id, "LEAVE_APPROVED") in recipients
    assert (users["lead"].account_id, "LEAVE_APPROVED") in recipients
    assert (users["pm"].account_id, "STAFF_LEAVE_APPROVED") in recipients


def test_approval_audit_contains_prior_and_new_status(leave_api):
    client, db, _, users, _, leave_type = leave_api
    request = add_request(db, leave_type)

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={})

    assert response.status_code == 200
    audit = db.query(AuditLog).filter_by(entity_name="LEAVE_REQUEST", entity_ref_id=str(request.leave_id)).one()
    assert audit.action == AuditAction.APPROVE
    assert audit.account_id == users["lead"].account_id
    assert json.loads(audit.old_value) == {"status": "PENDING"}
    assert json.loads(audit.new_value) == {"status": "APPROVED", "review_remarks": None}


def test_approve_revalidates_quota_after_policy_change(leave_api):
    client, db, _, _, _, leave_type = leave_api
    request = add_request(db, leave_type, days=3)
    leave_type.yearly_quota = 2
    db.commit()

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={})

    assert response.status_code == 400
    assert "Insufficient leave balance" in response.json()["detail"]
    assert db.get(LeaveRequest, request.leave_id).status == LeaveStatus.PENDING
    assert db.query(Notification).count() == 0


def test_approve_rechecks_overlap_before_decision(leave_api):
    client, db, _, _, _, leave_type = leave_api
    request = add_request(db, leave_type)
    add_request(db, leave_type, start=date(2026, 12, 8), end=date(2026, 12, 10), days=3, status=LeaveStatus.APPROVED)

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={})

    assert response.status_code == 409
    assert db.get(LeaveRequest, request.leave_id).status == LeaveStatus.PENDING


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_tl_outside_applicant_team_cannot_decide(leave_api, decision):
    client, db, actor, users, _, leave_type = leave_api
    request = add_request(db, leave_type, emp_id=2)
    actor["user"] = users["lead"]
    payload = {"review_remarks": "Unable to approve this request."} if decision == "reject" else {}

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/{decision}", json=payload)

    assert response.status_code == 403
    assert db.get(LeaveRequest, request.leave_id).status == LeaveStatus.PENDING


def test_self_approval_is_forbidden(leave_api):
    client, db, actor, _, _, leave_type = leave_api
    request = add_request(db, leave_type, emp_id=3)

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/approve", json={})

    assert response.status_code == 403
    assert "own leave" in response.json()["detail"]


@pytest.mark.parametrize("status_value", [LeaveStatus.APPROVED, LeaveStatus.REJECTED])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_already_processed_request_returns_400(leave_api, status_value, decision):
    client, db, _, _, _, leave_type = leave_api
    request = add_request(db, leave_type, status=status_value)
    payload = {"review_remarks": "This request was previously reviewed."} if decision == "reject" else {}

    response = client.put(f"/api/v1/leave/requests/{request.leave_id}/{decision}", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Request already processed"
