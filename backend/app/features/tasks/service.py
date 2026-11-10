from typing import Optional
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.notifications.service import NotificationService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import TaskAssignRequest, TaskResponse
from app.models.enums import AuditAction, UserType
from app.models.employee import Employee
from app.models.task import Task
from app.models.team import Team
from app.models.user_account import UserAccount


class TaskNotFoundError(Exception):
    pass


class AssigneeNotFoundError(Exception):
    pass


class AssigneeNotEligibleError(Exception):
    pass


class TaskAssignmentForbiddenError(Exception):
    pass


class TaskService:
    """Business logic for task management (US-09, US-14)."""

    @staticmethod
    def _resolve_employee_for_account(db: Session, account_id) -> Optional[Employee]:
        """Look up the employee record matching a user account."""
        if not account_id:
            return None
        return db.query(Employee).filter(Employee.account_id == account_id).first()

    @staticmethod
    def check_can_manage_task(db: Session, current_user: UserAccount, task: Task) -> None:
        """
        Verify that the user is authorized to assign or reassign this task.
        Authorized roles: ADMIN, PM, TEAM_LEAD, or EMPLOYEE who is lead of the task's team/project.
        """
        user_type_val = (
            current_user.user_type.value
            if hasattr(current_user.user_type, "value")
            else str(current_user.user_type)
        ).upper()

        # Admin and Project Manager have management authority
        if user_type_val in ("ADMIN", "PM", "PROJECT_MANAGER"):
            return

        # Check elevated active grants if baseline is employee
        from datetime import datetime, timezone
        from app.models.elevated_access_grant import ElevatedAccessGrant

        now = datetime.now(timezone.utc)
        active_grant = (
            db.query(ElevatedAccessGrant)
            .filter(
                ElevatedAccessGrant.user_id == current_user.account_id,
                ElevatedAccessGrant.revoked_at.is_(None),
                ElevatedAccessGrant.expires_at > now,
            )
            .first()
        )
        if active_grant:
            elevated_role = active_grant.granted_role.strip().upper()
            if elevated_role in ("ADMIN", "PM", "PROJECT_MANAGER", "TEAM_LEAD"):
                return

        # Check if user is a designated TEAM_LEAD or an EMPLOYEE who leads the task's team/project
        if user_type_val in ("TEAM_LEAD", "EMPLOYEE"):
            emp = TaskService._resolve_employee_for_account(db, current_user.account_id)
            if emp:
                # 1. If task has a team_id, check if employee is the team lead
                if task.team_id is not None:
                    team = db.query(Team).filter(Team.team_id == task.team_id).first()
                    if team and team.lead_emp_id == emp.emp_id:
                        return

                # 2. Check if employee leads any team on the task's project
                project_team_lead = (
                    db.query(Team)
                    .filter(Team.project_id == task.project_id, Team.lead_emp_id == emp.emp_id)
                    .first()
                )
                if project_team_lead:
                    return

        raise TaskAssignmentForbiddenError("You are not authorized to assign or manage this task.")

    @staticmethod
    def assign_task(
        db: Session,
        task_id: int,
        payload: TaskAssignRequest,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> TaskResponse:
        """
        Assign an unassigned task to an employee (US-09).
        Verifies task existence, manager authorization, and assignee eligibility within the team.
        Dispatches TASK_ASSIGNED notification and writes an audit log.
        """
        # 1. Fetch task
        task = TaskRepository.get_task_by_id(db, task_id=task_id)
        if not task:
            raise TaskNotFoundError(f"Task with ID {task_id} not found.")

        # 2. Authorize caller
        TaskService.check_can_manage_task(db, current_user=current_user, task=task)

        # 3. Fetch target assignee
        assignee = TaskRepository.get_employee_by_id(db, emp_id=payload.assignee_id)
        if not assignee:
            raise AssigneeNotFoundError(f"Employee with ID {payload.assignee_id} not found.")

        # 4. Verify assignee belongs to task's team/project
        if not TaskRepository.is_employee_eligible_assignee(db, emp_id=assignee.emp_id, task=task):
            raise AssigneeNotEligibleError(
                f"Employee with ID {payload.assignee_id} is not an active member of the task team."
            )

        old_assignee_id = task.assigned_to

        # 5. Persist assignment
        updated_task = TaskRepository.assign_task(db, task=task, assignee_id=assignee.emp_id)

        # 6. Audit log entry
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=current_user.account_id,
            old_value={"assigned_to": old_assignee_id},
            new_value={"assigned_to": assignee.emp_id},
            ip_address=ip_address,
        )

        # 7. Notification trigger
        if assignee.account_id:
            NotificationService.create_notification(
                db=db,
                user_id=assignee.account_id,
                type="TASK_ASSIGNED",
                title="New Task Assigned",
                message=f"You have been assigned to task #{task.task_id}: '{task.title}'",
                link=f"/tasks/{task.task_id}",
            )
            db.commit()

        return TaskResponse.model_validate(updated_task)
