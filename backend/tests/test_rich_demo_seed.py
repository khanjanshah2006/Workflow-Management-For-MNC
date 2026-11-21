import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.features.projects.risk_service import ProjectRiskService
from app.features.tasks.overdue import OverdueService
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, LeaveStatus, ProjectStatus, TaskStatus, UserType
from app.models.executive_report import ExecutiveReport
from app.models.leave import LeaveRequest
from app.models.project import Project
from app.models.support import SupportTicket
from app.models.task import Task
from app.models.user_account import UserAccount

TODAY = date(2026, 11, 18)


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


@pytest.fixture
def seed(monkeypatch, tmp_path):
    """The seed module defaults DATABASE_URL on import; set it here so nothing leaks past the test."""
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    return importlib.import_module("scripts.seed_rich_demo").seed_rich_demo


def _counts(db):
    return {t.name: db.execute(text(f"select count(*) from {t.name}")).scalar() for t in Base.metadata.sorted_tables}


def _present(db, column):
    return {value.value if hasattr(value, "value") else value for value in db.scalars(select(column).distinct())}


def test_rich_demo_seed_is_idempotent_and_covers_every_role_and_status(db, seed):
    seed(db, today=TODAY, password="Seed@123")
    first = _counts(db)
    seed(db, today=TODAY, password="Seed@123")
    assert _counts(db) == first
    later = TODAY + timedelta(days=7)
    seed(db, today=later, password="Seed@123")
    assert _counts(db) == first

    active_types = set(db.scalars(select(UserAccount.user_type).where(UserAccount.is_active.is_(True))))
    assert active_types == set(UserType)
    assert _present(db, Task.status) == {s.value for s in TaskStatus}
    assert _present(db, LeaveRequest.status) == {s.value for s in LeaveStatus}
    assert _present(db, Project.status) == {s.value for s in ProjectStatus}
    assert _present(db, SupportTicket.status) >= {"open", "in_progress", "escalated", "resolved", "closed"}
    assert db.scalar(select(func.count()).select_from(Task)) >= 100

    def rejections(task):
        rows = db.scalars(select(AuditLog.new_value).where(
            AuditLog.entity_name == "TASK", AuditLog.entity_ref_id == str(task.task_id),
            AuditLog.action == AuditAction.UPDATE,
        ))
        return sum(1 for value in rows if json.loads(value).get("status") == "REJECTED")

    repeated = db.scalars(select(Task).where(Task.rejection_count >= 2)).all()
    assert any(rejections(task) >= 2 for task in repeated)

    overdue = OverdueService.base_query(db, later)
    assert db.scalar(select(func.count()).select_from(overdue.subquery())) >= 15

    admin = db.scalar(select(UserAccount).where(UserAccount.email == "admin@company.com"))
    phoenix = db.scalar(select(Project).where(Project.project_code == "PHOENIX-MOB"))
    dashboard = ProjectRiskService.get_dashboard(db, phoenix.project_id, admin, later)
    assert dashboard["at_risk_milestones_count"] >= 1

    reports = db.scalars(select(ExecutiveReport)).all()
    assert len(reports) == 3
    assert all(Path(report.file_path).is_file() for report in reports)
