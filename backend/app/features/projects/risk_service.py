"""PM risk & quality dashboard (S5-BE-2: US-23, US-38, US-39).

Read-only aggregates for one project. ``today`` is always injected so callers
and tests control the reference date.
"""
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.scope import get_int_param
from app.features.employees.repository import EmployeeRepository
from app.features.projects.service import ProjectNotFoundError, ProjectService
from app.features.tasks.overdue import OverdueService
from app.models.audit_log import AuditLog
from app.models.employee import Employee
from app.models.enums import AuditAction, MilestoneStatus, TaskStatus, UserType
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.task import Task
from app.models.user_account import UserAccount

REJECTION_THRESHOLD_KEY = "REPEATED_REJECTION_THRESHOLD"
DEFAULT_REJECTION_THRESHOLD = 2
AT_RISK_WINDOW_DAYS = 3
UPCOMING_WINDOW_DAYS = 14
# Risk score bands: LOW < 4 <= MEDIUM < 10 <= HIGH
RISK_MEDIUM_FROM = 4
RISK_HIGH_FROM = 10


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
    def rejection_history(db: Session, task_ids: list[int]) -> dict[int, list[dict]]:
        """Rejections per task, oldest first, from the audit rows TaskService.review_task writes.

        One query for all tasks: entity TASK, action UPDATE, new_value.status == REJECTED.
        """
        history: dict[int, list[dict]] = defaultdict(list)
        if not task_ids:
            return history
        rows = db.execute(
            select(AuditLog.entity_ref_id, AuditLog.new_value, AuditLog.created_at)
            .where(
                AuditLog.entity_name == "TASK",
                AuditLog.action == AuditAction.UPDATE,
                AuditLog.entity_ref_id.in_([str(t) for t in task_ids]),
            )
            .order_by(AuditLog.created_at, AuditLog.log_id)
        ).all()
        for ref_id, new_value, created_at in rows:
            try:
                payload = json.loads(new_value or "")
            except ValueError:
                continue
            if isinstance(payload, dict) and payload.get("status") == TaskStatus.REJECTED.value:
                history[int(ref_id)].append(
                    {"rejected_at": created_at, "feedback": payload.get("rejection_feedback")}
                )
        return history

    @staticmethod
    def repeatedly_rejected_tasks(
        db: Session,
        project_id: int,
        threshold: int,
        assignee_id: Optional[int] = None,
        include_done: bool = False,
    ) -> list[dict]:
        """Tasks with rejection_count >= threshold, each with its full rejection history."""
        stmt = (
            select(Task, Employee.full_name)
            .outerjoin(Employee, Employee.emp_id == Task.assigned_to)
            .where(Task.project_id == project_id, Task.rejection_count >= threshold)
            .order_by(Task.rejection_count.desc(), Task.task_id)
        )
        if assignee_id is not None:
            stmt = stmt.where(Task.assigned_to == assignee_id)
        if not include_done:
            stmt = stmt.where(Task.status != TaskStatus.DONE)
        rows = db.execute(stmt).all()

        history = ProjectRiskService.rejection_history(db, [task.task_id for task, _ in rows])
        return [
            {
                "task_id": task.task_id,
                "title": task.title,
                "assignee_id": task.assigned_to,
                "assignee_name": assignee_name,
                "rejection_count": task.rejection_count,
                "status": task.status,
                "latest_rejection_feedback": task.rejection_feedback,
                "rejection_history": history.get(task.task_id, []),
            }
            for task, assignee_name in rows
        ]

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
    def blocked_tasks(db: Session, project_id: int, assignee_id: Optional[int] = None) -> list[dict]:
        stmt = (
            select(Task, Employee.full_name)
            .outerjoin(Employee, Employee.emp_id == Task.assigned_to)
            .where(Task.project_id == project_id, Task.status == TaskStatus.BLOCKED)
            .order_by(Task.updated_at, Task.task_id)
        )
        if assignee_id is not None:
            stmt = stmt.where(Task.assigned_to == assignee_id)
        return [
            {
                "task_id": task.task_id,
                "title": task.title,
                "assignee_name": assignee_name,
                "blocker_reason": task.blocker_reason,
                # No dedicated column; updated_at is the best available signal.
                "blocked_since": task.updated_at,
            }
            for task, assignee_name in db.execute(stmt).all()
        ]

    @staticmethod
    def risk_points(overdue: int, blocked: int, repeatedly_rejected: int, milestones_at_risk_or_overdue: int) -> int:
        return 2 * overdue + 2 * blocked + repeatedly_rejected + 3 * milestones_at_risk_or_overdue

    @staticmethod
    def risk_level(points: int) -> str:
        if points < RISK_MEDIUM_FROM:
            return "LOW"
        if points < RISK_HIGH_FROM:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def get_risks(
        db: Session,
        project_id: int,
        user: UserAccount,
        today: date,
        assignee_id: Optional[int] = None,
        include_done: bool = False,
    ) -> dict:
        """Risk lists for the project. The score is project-wide; assignee_id only narrows the lists."""
        ProjectRiskService.get_authorized_project(db, project_id, user)
        threshold = ProjectRiskService.rejection_threshold(db)
        at_risk = ProjectRiskService.at_risk_milestones(db, project_id, today)
        points = ProjectRiskService.risk_points(
            overdue=ProjectRiskService.overdue_tasks_count(db, project_id, today),
            blocked=ProjectRiskService.status_counts(db, project_id)[TaskStatus.BLOCKED.value],
            repeatedly_rejected=ProjectRiskService.repeatedly_rejected_count(db, project_id, threshold),
            milestones_at_risk_or_overdue=len(at_risk)
            + ProjectRiskService.overdue_milestones_count(db, project_id, today),
        )
        return {
            "project_id": project_id,
            "risk_score": ProjectRiskService.risk_level(points),
            "risk_points": points,
            "rejection_threshold": threshold,
            "repeatedly_rejected_tasks": ProjectRiskService.repeatedly_rejected_tasks(
                db, project_id, threshold, assignee_id=assignee_id, include_done=include_done
            ),
            "blocked_tasks": ProjectRiskService.blocked_tasks(db, project_id, assignee_id=assignee_id),
            "at_risk_milestones": at_risk,
        }

    @staticmethod
    def get_team_workload(db: Session, project_id: int, user: UserAccount) -> list[dict]:
        """US-39: one row per actively staffed employee, cross-project aggregates only.

        Cross-project numbers reuse EmployeeRepository.get_batch_workload_metrics so the
        definitions match GET /employees/{id}/workload. Never returns other projects' tasks.
        """
        ProjectRiskService.get_authorized_project(db, project_id, user)
        staff = db.execute(
            select(Employee.emp_id, Employee.full_name, ProjectAssignment.role_in_project)
            .join(ProjectAssignment, ProjectAssignment.emp_id == Employee.emp_id)
            .where(ProjectAssignment.project_id == project_id, ProjectAssignment.released_on.is_(None))
            .order_by(Employee.full_name, Employee.emp_id)
        ).all()
        emp_ids = [emp_id for emp_id, _, _ in staff]
        if not emp_ids:
            return []

        in_project = dict(
            db.execute(
                select(Task.assigned_to, func.count())
                .where(
                    Task.project_id == project_id,
                    Task.assigned_to.in_(emp_ids),
                    Task.status != TaskStatus.DONE,
                )
                .group_by(Task.assigned_to)
            ).all()
        )
        overall = EmployeeRepository.get_batch_workload_metrics(db, emp_ids)
        return [
            {
                "emp_id": emp_id,
                "full_name": full_name,
                "role_in_project": role,
                "open_tasks_in_project": in_project.get(emp_id, 0),
                "open_tasks_all_projects": overall[emp_id]["open_tasks_count"],
                "active_projects_count": overall[emp_id]["active_projects_count"],
                "utilization_pct": overall[emp_id]["utilization_pct"],
            }
            for emp_id, full_name, role in staff
        ]

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
