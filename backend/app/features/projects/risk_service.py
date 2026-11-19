"""PM risk & quality dashboard (S5-BE-2: US-23, US-38, US-39).

Read-only aggregates for one project. ``today`` is always injected so callers
and tests control the reference date.
"""
from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.scope import get_int_param
from app.features.projects.service import ProjectNotFoundError, ProjectService
from app.features.tasks.overdue import OverdueService
from app.models.enums import MilestoneStatus, TaskStatus, UserType
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.task import Task
from app.models.user_account import UserAccount

REJECTION_THRESHOLD_KEY = "REPEATED_REJECTION_THRESHOLD"
DEFAULT_REJECTION_THRESHOLD = 2
AT_RISK_WINDOW_DAYS = 3
UPCOMING_WINDOW_DAYS = 14


class ProjectRiskService:
    @staticmethod
    def get_authorized_project(db: Session, project_id: int, user: UserAccount) -> Project:
        """404 if the project is missing, then 403 unless the caller owns it or is an admin."""
        project = db.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        # _verify_pm_ownership exempts ADMIN only; this feature also admits SYSTEM_ADMIN.
        if user.user_type != UserType.SYSTEM_ADMIN:
            ProjectService._verify_pm_ownership(db, project, user)
        return project

    @staticmethod
    def rejection_threshold(db: Session) -> int:
        return get_int_param(db, REJECTION_THRESHOLD_KEY, DEFAULT_REJECTION_THRESHOLD)

    @staticmethod
    def status_counts(db: Session, project_id: int) -> dict[str, int]:
        """Task counts per status in one GROUP BY; every status is present."""
        rows = db.execute(
            select(Task.status, func.count())
            .where(Task.project_id == project_id)
            .group_by(Task.status)
        ).all()
        counts = {s.value: 0 for s in TaskStatus}
        for task_status, count in rows:
            counts[TaskStatus(task_status).value] = count
        return counts

    @staticmethod
    def overdue_tasks_count(db: Session, project_id: int, today: date) -> int:
        stmt = OverdueService.base_query(db, today).where(Task.project_id == project_id)
        return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    @staticmethod
    def repeatedly_rejected_count(db: Session, project_id: int, threshold: int) -> int:
        return db.scalar(
            select(func.count()).where(
                Task.project_id == project_id,
                Task.rejection_count >= threshold,
                Task.status != TaskStatus.DONE,
            )
        ) or 0

    @staticmethod
    def milestones_due_between(db: Session, project_id: int, start: date, end: date) -> list[dict]:
        """Pending, non-deleted milestones with start <= target_date <= end, plus open task counts."""
        rows = db.execute(
            select(
                ProjectMilestone.id,
                ProjectMilestone.title,
                ProjectMilestone.target_date,
                func.count(Task.task_id),
            )
            .outerjoin(
                Task,
                and_(Task.milestone_id == ProjectMilestone.id, Task.status != TaskStatus.DONE),
            )
            .where(
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted.is_(False),
                ProjectMilestone.status == MilestoneStatus.PENDING,
                ProjectMilestone.target_date >= start,
                ProjectMilestone.target_date <= end,
            )
            .group_by(ProjectMilestone.id, ProjectMilestone.title, ProjectMilestone.target_date)
            .order_by(ProjectMilestone.target_date, ProjectMilestone.id)
        ).all()
        return [
            {"milestone_id": mid, "title": title, "target_date": target, "open_tasks": open_tasks}
            for mid, title, target, open_tasks in rows
        ]

    @staticmethod
    def at_risk_milestones(db: Session, project_id: int, today: date) -> list[dict]:
        """Pending milestones due within 3 days that still have open tasks."""
        window = ProjectRiskService.milestones_due_between(
            db, project_id, today, today + timedelta(days=AT_RISK_WINDOW_DAYS)
        )
        return [m for m in window if m["open_tasks"] >= 1]

    @staticmethod
    def overdue_milestones_count(db: Session, project_id: int, today: date) -> int:
        return db.scalar(
            select(func.count()).where(
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted.is_(False),
                ProjectMilestone.status == MilestoneStatus.PENDING,
                ProjectMilestone.target_date < today,
            )
        ) or 0

    @staticmethod
    def get_dashboard(db: Session, project_id: int, user: UserAccount, today: date) -> dict:
        project = ProjectRiskService.get_authorized_project(db, project_id, user)
        counts = ProjectRiskService.status_counts(db, project_id)
        total = sum(counts.values())
        threshold = ProjectRiskService.rejection_threshold(db)
        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "status": project.status,
            "completion_pct": round(counts[TaskStatus.DONE.value] / total * 100) if total else 0,
            "total_tasks": total,
            "tasks_by_status": counts,
            "overdue_tasks_count": ProjectRiskService.overdue_tasks_count(db, project_id, today),
            "blocked_tasks_count": counts[TaskStatus.BLOCKED.value],
            "at_risk_milestones_count": len(ProjectRiskService.at_risk_milestones(db, project_id, today)),
            "overdue_milestones_count": ProjectRiskService.overdue_milestones_count(db, project_id, today),
            "repeatedly_rejected_count": ProjectRiskService.repeatedly_rejected_count(db, project_id, threshold),
            "rejection_threshold": threshold,
            "upcoming_milestones": ProjectRiskService.milestones_due_between(
                db, project_id, today, today + timedelta(days=UPCOMING_WINDOW_DAYS)
            ),
        }
