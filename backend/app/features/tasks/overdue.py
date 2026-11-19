"""Overdue task detection and escalation (S5, US-15 / US-19).

A task is overdue when it has a due date earlier than ``today``, is not DONE,
and belongs to a project that is not CANCELLED. ``today`` is always injected so
that callers (and tests) control the reference date.
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, aliased

from app.core import notification_types
from app.core.audit import write_audit_log
from app.core.scope import led_team_ids, resolve_employee, resolve_pm
from app.features.notifications.service import NotificationService
from app.models.employee import Employee
from app.models.enums import AuditAction, PriorityLevel, ProjectStatus, TaskStatus, UserType
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.task import Task
from app.models.team import Team
from app.models.user_account import UserAccount

_ALL_SCOPE_ROLES = {UserType.ADMIN, UserType.SYSTEM_ADMIN}

# Enum values sort alphabetically, so rank priority explicitly (CRITICAL first).
_PRIORITY_RANK = case(
    (Task.priority == PriorityLevel.CRITICAL, 0),
    (Task.priority == PriorityLevel.HIGH, 1),
    (Task.priority == PriorityLevel.MEDIUM, 2),
    (Task.priority == PriorityLevel.LOW, 3),
    else_=4,
)


def days_overdue(due_date: date, today: date) -> int:
    return (today - due_date).days


class OverdueService:
    @staticmethod
    def base_query(db: Session, today: date) -> Select:
        """Shared overdue predicate (also used by S5-BE-2). Selects Task rows."""
        return (
            select(Task)
            .join(Project, Project.project_id == Task.project_id)
            .where(
                Task.due_date.is_not(None),
                Task.due_date < today,
                Task.status != TaskStatus.DONE,
                Project.status != ProjectStatus.CANCELLED,
            )
        )

    @staticmethod
    def _apply_scope(db: Session, stmt: Select, actor: UserAccount) -> Optional[Select]:
        """Restrict to the caller's visibility. Returns None when the caller sees nothing."""
        role = actor.user_type
        if role in _ALL_SCOPE_ROLES:
            return stmt
        if role == UserType.TEAM_LEAD:
            emp = resolve_employee(db, actor)
            team_ids = led_team_ids(db, emp.emp_id) if emp else set()
            return stmt.where(Task.team_id.in_(team_ids)) if team_ids else None
        if role == UserType.PM:
            pm = resolve_pm(db, actor)
            return stmt.where(Project.pm_id == pm.pm_id) if pm else None
        return None

    @staticmethod
    def list_overdue(
        db: Session,
        actor: UserAccount,
        today: date,
        project_id: Optional[int] = None,
        team_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        priority: Optional[PriorityLevel] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        stmt = OverdueService._apply_scope(db, OverdueService.base_query(db, today), actor)
        if stmt is None:
            return {"total_overdue": 0, "page": page, "limit": limit, "items": []}

        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        if team_id is not None:
            stmt = stmt.where(Task.team_id == team_id)
        if assignee_id is not None:
            stmt = stmt.where(Task.assigned_to == assignee_id)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        lead = aliased(Employee)
        assignee = aliased(Employee)
        rows = db.execute(
            stmt.with_only_columns(
                Task,
                Project.name,
                lead.full_name,
                assignee.full_name,
                ProjectMilestone.title,
            )
            .outerjoin(Team, Team.team_id == Task.team_id)
            .outerjoin(lead, lead.emp_id == Team.lead_emp_id)
            .outerjoin(assignee, assignee.emp_id == Task.assigned_to)
            .outerjoin(ProjectMilestone, ProjectMilestone.id == Task.milestone_id)
            # Earliest due date == most days overdue.
            .order_by(Task.due_date.asc(), _PRIORITY_RANK, Task.task_id)
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()

        items = [
            {
                "task_id": task.task_id,
                "title": task.title,
                "project_id": task.project_id,
                "project_name": project_name,
                "team_id": task.team_id,
                "team_lead_name": lead_name,
                "assignee_id": task.assigned_to,
                "assignee_name": assignee_name,
                "milestone_title": milestone_title,
                "due_date": task.due_date,
                "days_overdue": days_overdue(task.due_date, today),
                "priority": task.priority,
                "status": task.status,
                "progress_pct": task.progress_pct,
            }
            for task, project_name, lead_name, assignee_name, milestone_title in rows
        ]
        return {"total_overdue": total, "page": page, "limit": limit, "items": items}

    @staticmethod
    def run_sweep(
        db: Session,
        actor: UserAccount,
        today: date,
        now: Optional[datetime] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Notify TL + assignee once per overdue episode, then commit once.

        Idempotency: tasks with ``overdue_notified_at`` already set are skipped.
        Clearing the flag (see ``apply_due_date_change``) opens a new episode.
        """
        now = now or datetime.now(timezone.utc)
        lead = aliased(Employee)
        assignee = aliased(Employee)
        rows = db.execute(
            OverdueService.base_query(db, today)
            .add_columns(lead.account_id, assignee.account_id)
            .outerjoin(Team, Team.team_id == Task.team_id)
            .outerjoin(lead, lead.emp_id == Team.lead_emp_id)
            .outerjoin(assignee, assignee.emp_id == Task.assigned_to)
            .order_by(Task.task_id)
        ).all()

        newly_flagged = 0
        already_flagged = 0
        notifications_sent = 0
        for task, lead_account_id, assignee_account_id in rows:
            if task.overdue_notified_at is not None:
                already_flagged += 1
                continue
            notifications_sent += OverdueService._notify(
                db, task, today, lead_account_id, assignee_account_id
            )
            task.overdue_notified_at = now
            newly_flagged += 1

        result = {
            "evaluated_tasks": len(rows),
            "newly_flagged_overdue": newly_flagged,
            "already_flagged": already_flagged,
        }
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK_OVERDUE_SWEEP",
            entity_ref_id="sweep",
            account_id=actor.account_id,
            new_value={**result, "notifications_sent": notifications_sent, "as_of": today.isoformat()},
            ip_address=ip_address,
            commit=False,
        )
        db.commit()
        return result

    @staticmethod
    def _notify(
        db: Session,
        task: Task,
        today: date,
        lead_account_id: Optional[UUID],
        assignee_account_id: Optional[UUID],
    ) -> int:
        days = days_overdue(task.due_date, today)
        link = f"/tasks/{task.task_id}"
        sent = 0
        if lead_account_id is not None:
            NotificationService.create_notification(
                db=db,
                user_id=lead_account_id,
                type=notification_types.TASK_OVERDUE,
                title="Task Overdue",
                message=f"Task #{task.task_id} '{task.title}' is {days} day(s) overdue (due {task.due_date.isoformat()}).",
                link=link,
            )
            sent += 1
        if assignee_account_id is not None:
            NotificationService.create_notification(
                db=db,
                user_id=assignee_account_id,
                type=notification_types.TASK_DEADLINE_MISSED,
                title="Deadline Missed",
                message=f"You missed the deadline for task #{task.task_id} '{task.title}' (due {task.due_date.isoformat()}).",
                link=link,
            )
            sent += 1
        return sent


def apply_due_date_change(task: Task, new_due_date: Optional[date]) -> None:
    """Set a task's due date and reset its overdue episode when it changes.

    Every code path that edits ``Task.due_date`` (S4-BE-5 and future task
    edits) must go through this so the next sweep can notify again.
    """
    if task.due_date != new_due_date:
        task.due_date = new_due_date
        task.overdue_notified_at = None
