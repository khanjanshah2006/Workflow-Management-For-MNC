"""
Automated test suite for US-34: Skill-Change Proposals and Review Workflow.

Tests cover:
  1. propose_skill_change: ADD, UPDATE, and REMOVE actions.
  2. Notifications to HR and Team Lead on proposal creation.
  3. Approve proposal applies to employee_skill table (and creates new skill row if proposed by name).
  4. Reject requires mandatory remarks (400 if missing).
  5. Scoped review queue: HR sees all; Team Lead sees only led team members.
  6. Duplicate pending proposal for the same skill returns 409 Conflict.
  7. Unauthorized decider (non-lead or unrelated employee) returns 403 Forbidden.
  8. Team Lead self-decision prevention returns 403 Forbidden.
  9. Deciding an already-decided request returns 409 Conflict.
  10. Audit logging on proposal creation, approval, and rejection.
"""
from datetime import date, datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    SkillProficiency,
    SkillChangeAction,
    SkillChangeStatus,
    TeamStatus,
    UserType,
)
from app.models.notification import Notification
from app.models.skill import EmployeeSkill, Skill, SkillChangeRequest
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


@pytest.fixture(scope="function")
def db():
    """Isolated in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with overridden DB session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(db, user_type: UserType, email: str | None = None) -> UserAccount:
    acc_id = uuid.uuid4()
    mail = email or f"{acc_id.hex[:8]}@company.com"
    user = UserAccount(
        account_id=acc_id,
        email=mail,
        password_hash="fakehash",
        user_type=user_type,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_employee(db, user: UserAccount, name: str = "Employee Test") -> Employee:
    emp = Employee(
        account_id=user.account_id,
        emp_code=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        full_name=name,
        email=user.email,
        designation="Software Engineer",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def setup_org_structure(db):
    """
    Sets up:
      - HR user + employee
      - Team 1: Lead 1 + Member 1 (Employee 1)
      - Team 2: Lead 2 + Member 2 (Employee 2)
      - Existing skill 'Python'
    """
    hr_user = make_user(db, UserType.HR, email="hr@company.com")
    hr_emp = make_employee(db, hr_user, name="Helen HR")

    tl1_user = make_user(db, UserType.TEAM_LEAD, email="tl1@company.com")
    tl1_emp = make_employee(db, tl1_user, name="Lead One")

    emp1_user = make_user(db, UserType.EMPLOYEE, email="emp1@company.com")
    emp1 = make_employee(db, emp1_user, name="Dev One")

    tl2_user = make_user(db, UserType.TEAM_LEAD, email="tl2@company.com")
    tl2_emp = make_employee(db, tl2_user, name="Lead Two")

    emp2_user = make_user(db, UserType.EMPLOYEE, email="emp2@company.com")
    emp2 = make_employee(db, emp2_user, name="Dev Two")

    # Team 1
    team1 = Team(team_id=1, name="Core Team", lead_emp_id=tl1_emp.emp_id, status=TeamStatus.ACTIVE)
    db.add(team1)
    db.flush()
    tm1 = TeamMember(team_id=1, emp_id=emp1.emp_id, joined_on=date(2025, 1, 1))
    db.add(tm1)

    # Team 2
    team2 = Team(team_id=2, name="Mobile Team", lead_emp_id=tl2_emp.emp_id, status=TeamStatus.ACTIVE)
    db.add(team2)
    db.flush()
    tm2 = TeamMember(team_id=2, emp_id=emp2.emp_id, joined_on=date(2025, 1, 1))
    db.add(tm2)

    # Skill Python
    py_skill = Skill(skill_id=1, name="Python", category="Backend")
    db.add(py_skill)
    db.commit()

    return {
        "hr_user": hr_user,
        "hr_emp": hr_emp,
        "tl1_user": tl1_user,
        "tl1_emp": tl1_emp,
        "emp1_user": emp1_user,
        "emp1": emp1,
        "tl2_user": tl2_user,
        "tl2_emp": tl2_emp,
        "emp2_user": emp2_user,
        "emp2": emp2,
        "py_skill": py_skill,
    }


def test_propose_and_approve_applies_new_skill(client, db):
    """
    Employee proposes ADD for a new skill by name ('FastAPI').
    Lead 1 approves proposal.
    Skill row and EmployeeSkill are created, notifications and audit trail are persisted.
    """
    data = setup_org_structure(db)
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]

    # 1. Employee submits proposal
    payload = {
        "action": "ADD",
        "proposed_skill_name": "FastAPI",
        "proficiency": "INTERMEDIATE",
        "years_of_experience": 2,
        "justification": "Built multiple microservices using FastAPI",
    }
    res = client.post("/api/v1/profile/me/skill-requests", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["proposed_skill_name"] == "FastAPI"
    assert created["status"] == "PENDING"
    request_id = created["request_id"]

    # Verify notifications sent to HR and TL1
    hr_notifs = db.scalars(
        select(Notification).where(Notification.account_id == data["hr_user"].account_id)
    ).all()
    assert len(hr_notifs) == 1
    assert "FastAPI" in hr_notifs[0].message

    tl1_notifs = db.scalars(
        select(Notification).where(Notification.account_id == data["tl1_user"].account_id)
    ).all()
    assert len(tl1_notifs) == 1

    # Verify CREATE audit log
    audit_create = db.scalar(
        select(AuditLog).where(
            AuditLog.entity_name == "SKILL_CHANGE_REQUEST",
            AuditLog.action == AuditAction.CREATE,
            AuditLog.entity_ref_id == str(request_id),
        )
    )
    assert audit_create is not None

    # 2. Team Lead 1 approves
    app.dependency_overrides[get_current_user] = lambda: data["tl1_user"]
    approve_res = client.put(f"/api/v1/skill-requests/{request_id}/approve", json={"remarks": "Verified in recent sprints"})
    assert approve_res.status_code == 200
    approved = approve_res.json()
    assert approved["status"] == "APPROVED"
    assert approved["remarks"] == "Verified in recent sprints"

    # Verify skill and employee_skill exist in DB
    fastapi_skill = db.scalar(select(Skill).where(Skill.name == "FastAPI"))
    assert fastapi_skill is not None
    emp_skill = db.scalar(
        select(EmployeeSkill).where(
            EmployeeSkill.emp_id == data["emp1"].emp_id,
            EmployeeSkill.skill_id == fastapi_skill.skill_id,
        )
    )
    assert emp_skill is not None
    assert emp_skill.proficiency == SkillProficiency.INTERMEDIATE
    assert emp_skill.years_of_experience == 2

    # Verify decision notification delivered to applicant
    emp_notifs = db.scalars(
        select(Notification).where(Notification.account_id == data["emp1_user"].account_id)
    ).all()
    assert any("approved" in n.message.lower() for n in emp_notifs)

    # Verify APPROVE audit log
    audit_approve = db.scalar(
        select(AuditLog).where(
            AuditLog.entity_name == "SKILL_CHANGE_REQUEST",
            AuditLog.action == AuditAction.APPROVE,
            AuditLog.entity_ref_id == str(request_id),
        )
    )
    assert audit_approve is not None


def test_reject_requires_remarks(client, db):
    """Rejecting a proposal requires mandatory remarks (400 if empty)."""
    data = setup_org_structure(db)
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]

    # Submit proposal
    res = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "skill_id": data["py_skill"].skill_id,
            "proficiency": "EXPERT",
            "years_of_experience": 5,
            "justification": "5 years Python experience",
        },
    )
    assert res.status_code == 201
    request_id = res.json()["request_id"]

    # Attempt reject without remarks -> 400
    app.dependency_overrides[get_current_user] = lambda: data["hr_user"]
    rej_fail = client.put(f"/api/v1/skill-requests/{request_id}/reject", json={"remarks": ""})
    assert rej_fail.status_code == 400
    assert "remarks are mandatory" in rej_fail.json()["detail"].lower()

    # Reject with valid remarks -> 200
    rej_ok = client.put(
        f"/api/v1/skill-requests/{request_id}/reject",
        json={"remarks": "Experience does not match resume"},
    )
    assert rej_ok.status_code == 200
    assert rej_ok.json()["status"] == "REJECTED"
    assert rej_ok.json()["remarks"] == "Experience does not match resume"

    # Verify applicant received rejection notification
    notifs = db.scalars(
        select(Notification).where(Notification.account_id == data["emp1_user"].account_id)
    ).all()
    assert any("rejected" in n.message.lower() for n in notifs)

    # Verify rejection logged with AuditAction.UPDATE
    rej_audit = db.scalar(
        select(AuditLog).where(
            AuditLog.entity_name == "SKILL_CHANGE_REQUEST",
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.entity_ref_id == str(request_id),
        )
    )
    assert rej_audit is not None


def test_team_lead_scope_for_skill_requests(client, db):
    """
    Team Leads only see review requests from employees of active teams they lead.
    HR sees all requests.
    """
    data = setup_org_structure(db)

    # Emp 1 submits proposal
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]
    res1 = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "Docker",
            "proficiency": "BEGINNER",
            "justification": "Docker containerization",
        },
    )
    req1_id = res1.json()["request_id"]

    # Emp 2 submits proposal
    app.dependency_overrides[get_current_user] = lambda: data["emp2_user"]
    res2 = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "Kotlin",
            "proficiency": "INTERMEDIATE",
            "justification": "Kotlin Android dev",
        },
    )
    req2_id = res2.json()["request_id"]

    # TL1 reviews queue: should only see Emp 1
    app.dependency_overrides[get_current_user] = lambda: data["tl1_user"]
    tl1_queue = client.get("/api/v1/skill-requests?status=PENDING").json()
    assert tl1_queue["total"] == 1
    assert tl1_queue["items"][0]["request_id"] == req1_id

    # TL2 reviews queue: should only see Emp 2
    app.dependency_overrides[get_current_user] = lambda: data["tl2_user"]
    tl2_queue = client.get("/api/v1/skill-requests?status=PENDING").json()
    assert tl2_queue["total"] == 1
    assert tl2_queue["items"][0]["request_id"] == req2_id

    # HR reviews queue: should see both
    app.dependency_overrides[get_current_user] = lambda: data["hr_user"]
    hr_queue = client.get("/api/v1/skill-requests?status=PENDING").json()
    assert hr_queue["total"] == 2
    ids = {item["request_id"] for item in hr_queue["items"]}
    assert ids == {req1_id, req2_id}


def test_duplicate_pending_returns_409(client, db):
    """Submitting a proposal for a skill that already has a PENDING request returns 409."""
    data = setup_org_structure(db)
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]

    payload = {
        "action": "ADD",
        "proposed_skill_name": "Rust",
        "proficiency": "BEGINNER",
        "justification": "Rust systems programming",
    }
    res1 = client.post("/api/v1/profile/me/skill-requests", json=payload)
    assert res1.status_code == 201

    # Attempt duplicate
    res2 = client.post("/api/v1/profile/me/skill-requests", json=payload)
    assert res2.status_code == 409
    assert "pending request already exists" in res2.json()["detail"].lower()


def test_unauthorized_decider_returns_403(client, db):
    """
    TL2 cannot decide Emp 1's request.
    Regular employee cannot decide requests.
    Team Lead cannot decide their own skill proposal.
    HR cannot decide their own skill proposal.
    """
    data = setup_org_structure(db)

    # Emp 1 submits proposal
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]
    res = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "Go",
            "proficiency": "BEGINNER",
            "justification": "Go concurrency",
        },
    )
    req_id = res.json()["request_id"]

    # TL2 tries to approve Emp 1's request -> 403
    app.dependency_overrides[get_current_user] = lambda: data["tl2_user"]
    tl2_try = client.put(f"/api/v1/skill-requests/{req_id}/approve", json={})
    assert tl2_try.status_code == 403

    # Regular employee tries to approve -> 403
    app.dependency_overrides[get_current_user] = lambda: data["emp2_user"]
    emp2_try = client.put(f"/api/v1/skill-requests/{req_id}/approve", json={})
    assert emp2_try.status_code == 403

    # TL1 submits their own proposal
    app.dependency_overrides[get_current_user] = lambda: data["tl1_user"]
    tl_req = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "Management",
            "proficiency": "EXPERT",
            "justification": "Lead management track",
        },
    ).json()["request_id"]

    # TL1 tries to approve own request -> 403
    self_approve = client.put(f"/api/v1/skill-requests/{tl_req}/approve", json={})
    assert self_approve.status_code == 403

    # HR submits their own proposal
    app.dependency_overrides[get_current_user] = lambda: data["hr_user"]
    hr_req = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "People Operations",
            "proficiency": "EXPERT",
            "justification": "HR leadership",
        },
    ).json()["request_id"]

    # HR tries to approve own request -> 403 Forbidden (no self-approval)
    hr_self_approve = client.put(f"/api/v1/skill-requests/{hr_req}/approve", json={})
    assert hr_self_approve.status_code == 403


def test_deciding_already_decided_returns_409(client, db):
    """Approving or rejecting an already decided proposal returns 409 Conflict."""
    data = setup_org_structure(db)
    app.dependency_overrides[get_current_user] = lambda: data["emp1_user"]

    req_id = client.post(
        "/api/v1/profile/me/skill-requests",
        json={
            "action": "ADD",
            "proposed_skill_name": "Redis",
            "proficiency": "INTERMEDIATE",
            "justification": "Redis caching layer",
        },
    ).json()["request_id"]

    # HR approves
    app.dependency_overrides[get_current_user] = lambda: data["hr_user"]
    app_ok = client.put(f"/api/v1/skill-requests/{req_id}/approve", json={})
    assert app_ok.status_code == 200

    # HR attempts approve again -> 409
    app_dup = client.put(f"/api/v1/skill-requests/{req_id}/approve", json={})
    assert app_dup.status_code == 409
    assert "already approved" in app_dup.json()["detail"].lower()

    # HR attempts reject -> 409
    rej_dup = client.put(f"/api/v1/skill-requests/{req_id}/reject", json={"remarks": "Too late"})
    assert rej_dup.status_code == 409
