"""Idempotent Wave 3 demo seed (W3-BE-0).

Creates the accounts, project, team, leave and task data the Wave 3 browser
checks rely on. Rows are upserted by natural keys (email, code, name, title),
and every date is relative to `today`, so re-running it refreshes the demo
instead of duplicating it.

Usage (from backend/):
    python scripts/seed_wave3_demo.py

All accounts share the password in env SEED_PASSWORD (default: Password@123).
"""
import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__" and "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///wms_dev.db"

from sqlalchemy.orm import Session

import app.models  # noqa: F401  Register all models on metadata
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.deliverable import Deliverable
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    DeliverableStatus,
    LeaveStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.hr_manager import HRManager
from app.models.leave import LeaveRequest, LeaveType
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

DEFAULT_PASSWORD = "Password@123"
PROJECT_CODE = "ALPHA-ERP"


def _get_or_create(db: Session, model, lookup: dict, **values):
    """Return the row matching `lookup`, creating it if missing, then apply `values`."""
    row = db.query(model).filter_by(**lookup).first()
    if row is None:
        row = model(**lookup)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()
    return row


def _account(db: Session, email: str, user_type: UserType, password_hash: str) -> UserAccount:
    account = db.query(UserAccount).filter_by(email=email).first()
    if account is None:
        account = UserAccount(account_id=uuid.uuid4(), email=email)
        db.add(account)
    account.password_hash = password_hash
    account.user_type = user_type
    account.is_active = True
    db.flush()
    return account


def _business_days(start: date, end: date) -> int:
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def seed_wave3_demo(db: Session, today: date | None = None, password: str | None = None) -> None:
    today = today or date.today()
    pw_hash = hash_password(password or os.getenv("SEED_PASSWORD", DEFAULT_PASSWORD))
    now = datetime.now(timezone.utc)

    # Next week's Monday-Wednesday is the demo leave window.
    leave_start = today + timedelta(days=7 - today.weekday())
    leave_end = leave_start + timedelta(days=2)

    # Departments
    engineering = _get_or_create(db, Department, {"name": "Engineering"}, description="Product engineering")
    delivery = _get_or_create(db, Department, {"name": "Delivery"}, description="Project delivery and client services")

    # Employees (Team Lead + 3 members)
    people = {}
    for key, email, name, code, user_type, designation in (
        ("john", "john.teamlead@company.com", "John Doe", "W3-EMP-001", UserType.TEAM_LEAD, "Team Lead"),
        ("sarah", "sarah.connor@company.com", "Sarah Connor", "W3-EMP-002", UserType.EMPLOYEE, "Software Engineer"),
        ("matrix", "john.matrix@company.com", "John Matrix", "W3-EMP-003", UserType.EMPLOYEE, "Software Engineer"),
        ("kyle", "kyle.reese@company.com", "Kyle Reese", "W3-EMP-004", UserType.EMPLOYEE, "QA Engineer"),
    ):
        account = _account(db, email, user_type, pw_hash)
        people[key] = _get_or_create(
            db, Employee, {"email": email},
            account_id=account.account_id, dept_id=engineering.dept_id, emp_code=code,
            full_name=name, designation=designation, date_of_joining=date(2024, 1, 15),
        )
    john, sarah, matrix, kyle = people["john"], people["sarah"], people["matrix"], people["kyle"]

    # PM, HR, Executive, Client
    pm_account = _account(db, "pm@company.com", UserType.PM, pw_hash)
    pm = _get_or_create(
        db, ProjectManager, {"email": "pm@company.com"},
        account_id=pm_account.account_id, dept_id=delivery.dept_id, emp_code="W3-PM-001",
        full_name="Priya Menon", date_of_joining=date(2023, 6, 1),
    )
    hr_account = _account(db, "hr@company.com", UserType.HR, pw_hash)
    _get_or_create(
        db, HRManager, {"email": "hr@company.com"},
        account_id=hr_account.account_id, dept_id=delivery.dept_id, emp_code="W3-HR-001",
        full_name="Helen Ross", date_of_joining=date(2023, 3, 1),
    )
    _account(db, "executive@company.com", UserType.MNC_EXECUTIVE, pw_hash)
    client_account = _account(db, "client@acme.com", UserType.CLIENT, pw_hash)
    client = _get_or_create(
        db, Client, {"email": "client@acme.com"},
        account_id=client_account.account_id, company_name="Acme Corp", contact_person="Alice Carter",
    )

    # Project, milestones, team
    project = _get_or_create(
        db, Project, {"project_code": PROJECT_CODE},
        client_id=client.client_id, pm_id=pm.pm_id, name="Alpha ERP Modernization",
        description="Modernize Acme's legacy ERP platform.",
        start_date=today - timedelta(days=60), end_date=today + timedelta(days=120),
        priority=PriorityLevel.HIGH, status=ProjectStatus.ACTIVE, is_team_visible_to_client=True,
    )
    sprint1 = _get_or_create(
        db, ProjectMilestone, {"project_id": project.project_id, "title": "Sprint 1 Deliverables"},
        target_date=today - timedelta(days=14), status=MilestoneStatus.COMPLETED,
        completed_at=now - timedelta(days=14), is_deleted=False,
    )
    sprint2 = _get_or_create(
        db, ProjectMilestone, {"project_id": project.project_id, "title": "Sprint 2 Deliverables"},
        target_date=leave_end, status=MilestoneStatus.PENDING, completed_at=None, is_deleted=False,
    )
    _get_or_create(
        db, ProjectMilestone, {"project_id": project.project_id, "title": "UAT Sign-off"},
        target_date=today + timedelta(days=45), status=MilestoneStatus.PENDING, completed_at=None, is_deleted=False,
    )
    team = _get_or_create(
        db, Team, {"name": "Alpha Core Team"},
        project_id=project.project_id, lead_emp_id=john.emp_id, status=TeamStatus.ACTIVE,
        description="Core delivery team for Alpha ERP Modernization.",
    )
    for member in (sarah, matrix, kyle):
        _get_or_create(db, TeamMember, {"team_id": team.team_id, "emp_id": member.emp_id})
    for emp in (john, sarah, matrix, kyle):
        _get_or_create(
            db, ProjectAssignment, {"project_id": project.project_id, "emp_id": emp.emp_id},
            role_in_project="Team Lead" if emp is john else "Developer", released_on=None,
        )

    # Leave types
    annual = _get_or_create(db, LeaveType, {"name": "Annual"}, yearly_quota=20, is_paid=True, is_active=True)
    _get_or_create(db, LeaveType, {"name": "Sick"}, yearly_quota=10, is_paid=True, is_active=True)
    _get_or_create(db, LeaveType, {"name": "Casual"}, yearly_quota=5, is_paid=True, is_active=True)

    # Leave requests (keyed by employee + reason so dates can move with `today`)
    _get_or_create(
        db, LeaveRequest, {"emp_id": sarah.emp_id, "reason": "Attending a family event out of state."},
        leave_type_id=annual.leave_type_id, start_date=leave_start, end_date=leave_end,
        total_days=_business_days(leave_start, leave_end), status=LeaveStatus.PENDING,
        reviewed_by_account_id=None, reviewed_at=None, review_remarks=None,
    )
    _get_or_create(
        db, LeaveRequest, {"emp_id": kyle.emp_id, "reason": "Pre-planned vacation with family."},
        leave_type_id=annual.leave_type_id, start_date=leave_start, end_date=leave_start + timedelta(days=1),
        total_days=2, status=LeaveStatus.APPROVED,
        reviewed_by_account_id=john.account_id, reviewed_at=now, review_remarks="Approved. Enjoy your break.",
    )

    # Tasks
    def task(title: str, assignee: Employee, **values) -> Task:
        values.setdefault("milestone_id", None)
        values.setdefault("blocker_reason", None)
        values.setdefault("completed_at", None)
        values.setdefault("rejection_count", 0)
        values.setdefault("rejection_feedback", None)
        values.setdefault("overdue_notified_at", None)
        return _get_or_create(
            db, Task, {"project_id": project.project_id, "title": title},
            team_id=team.team_id, assigned_to=assignee.emp_id, created_by=john.emp_id, **values,
        )

    task("Implement JWT Refresh Token Flow", sarah, priority=PriorityLevel.HIGH,
         status=TaskStatus.IN_PROGRESS, progress_pct=40, milestone_id=sprint2.id,
         due_date=leave_start + timedelta(days=1))
    task("Migrate Legacy Invoice Module", matrix, priority=PriorityLevel.CRITICAL,
         status=TaskStatus.IN_PROGRESS, progress_pct=60, due_date=today - timedelta(days=5))
    task("Write API Integration Tests", kyle, priority=PriorityLevel.MEDIUM,
         status=TaskStatus.TODO, progress_pct=0, due_date=today - timedelta(days=3))
    task("Update Deployment Runbook", sarah, priority=PriorityLevel.LOW,
         status=TaskStatus.TODO, progress_pct=0, due_date=today - timedelta(days=1))
    feedback = [
        "Report totals do not match the ledger export.",
        "Currency rounding is still off for EUR invoices.",
        "Missing reconciliation for partial refunds.",
    ]
    rejected = task("Design Payment Reconciliation Report", matrix, priority=PriorityLevel.HIGH,
                    status=TaskStatus.REJECTED, progress_pct=90, due_date=today + timedelta(days=10),
                    rejection_count=len(feedback), rejection_feedback=feedback[-1])
    task("Integrate SSO Provider", kyle, priority=PriorityLevel.HIGH, status=TaskStatus.BLOCKED,
         progress_pct=30, due_date=today + timedelta(days=7),
         blocker_reason="Waiting on Acme IT to issue SSO client credentials.")
    task("Set Up CI Pipeline", john, priority=PriorityLevel.MEDIUM, status=TaskStatus.DONE,
         progress_pct=100, milestone_id=sprint1.id, due_date=today - timedelta(days=20),
         completed_at=now - timedelta(days=21))
    task("Database Schema Baseline", matrix, priority=PriorityLevel.MEDIUM, status=TaskStatus.DONE,
         progress_pct=100, milestone_id=sprint1.id, due_date=today - timedelta(days=18),
         completed_at=now - timedelta(days=19))

    # Rejection history lives in audit_log, in the same shape TaskService writes.
    has_history = (
        db.query(AuditLog)
        .filter_by(entity_name="TASK", entity_ref_id=str(rejected.task_id), action=AuditAction.UPDATE)
        .first()
    )
    if has_history is None:
        for count, text in enumerate(feedback, start=1):
            db.add(AuditLog(
                account_id=pm_account.account_id, action=AuditAction.UPDATE, entity_name="TASK",
                entity_ref_id=str(rejected.task_id),
                old_value=json.dumps({"status": "IN_REVIEW"}),
                new_value=json.dumps(
                    {"status": "REJECTED", "rejection_feedback": text, "rejection_count": count}
                ),
            ))

    # Client-visible deliverable
    _get_or_create(
        db, Deliverable, {"project_id": project.project_id, "title": "Sprint 1 Deliverable v1"},
        milestone_id=sprint1.id, submitted_by=john.emp_id, description="Sprint 1 build and release notes.",
        file_url="/uploads/deliverables/alpha-erp-sprint1-v1.pdf", version=1, status=DeliverableStatus.SUBMITTED,
    )

    db.commit()


def main() -> None:
    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_wave3_demo(db)
        print("Wave 3 demo data seeded. All demo accounts use SEED_PASSWORD (default Password@123).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
