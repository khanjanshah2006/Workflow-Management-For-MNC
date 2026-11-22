"""Service for leave-induced batch task reallocation (US-14, US-19, S4-BE-5)."""
from datetime import date, datetime, timezone
from typing import Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import roles, scope
from app.core.audit import write_audit_log
from app.core.notification_types import TASK_DEADLINE_EXTENDED
from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    ExtendedDeadlineTaskOut,
    ReassignedTaskOut,
    TaskReallocationActionIn,
    TaskReallocationActionType,
    TaskReallocationBatchIn,
    TaskReallocationBatchOut,
)
from app.features.notifications.service import NotificationService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.service import TaskService
from app.models.audit_log import AuditAction
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.enums import CommonStatus, LeaveStatus, TaskStatus
from app.models.leave import LeaveRequest
from app.models.user_account import UserAccount


class ReallocationValidationError(HTTPException):
    """Validation failure on a specific task during batch reallocation."""

    def __init__(self, status_code: int, detail: str, task_id: int):
        super().__init__(status_code=status_code, detail=detail)
        self.task_id = task_id


class LeaveReallocationService:
    """Service layer validating and applying batch task reallocations for leave applicants."""

    @classmethod
    def authorize_actor(
        cls,
        db: Session,
        current_user: UserAccount,
        leave_request: LeaveRequest,
    ) -> tuple[str, Optional[int]]:
        """
        Authorize the actor for batch task reallocation.
        Allowed roles:
        - ADMIN / SYSTEM_ADMIN: can reallocate any leave request's tasks.
        - TEAM_LEAD: must lead an active team containing the leave applicant.
        - PM: must manage the project of EVERY task in the batch (checked per task).
        Returns a tuple of (role_category, pm_id_or_lead_id).
        """
        user_type_str = (
            current_user.user_type.value
            if hasattr(current_user.user_type, "value")
            else str(current_user.user_type or "")
        ).upper()

        # Check elevated access grants (US-45)
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
        elevated_role = None
        if active_grant:
            elevated_role = active_grant.granted_role.strip().upper().replace(" ", "_")

        effective_role = elevated_role or user_type_str

        current_emp = scope.resolve_employee(db, current_user)
        is_admin = effective_role in ("ADMIN", "SYSTEM_ADMIN")
        is_pm = effective_role == roles.PM
        is_team_lead = effective_role == "TEAM_LEAD"

        if not is_team_lead and current_emp and effective_role == "EMPLOYEE":
            if scope.led_team_ids(db, current_emp.emp_id):
                is_team_lead = True

        if not (is_admin or is_pm or is_team_lead):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: requires one of ['TEAM_LEAD', 'PM', 'ADMIN']",
            )

        if is_admin:
            return "ADMIN", None

        if is_team_lead:
            if current_emp is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden: No employee profile found",
                )
            if not scope.is_team_lead_of(db, current_emp.emp_id, leave_request.emp_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden: You do not lead an active team containing the leave applicant",
                )
            return "TEAM_LEAD", current_emp.emp_id

        # PM check
        pm = scope.resolve_pm(db, current_user)
        if not pm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: No PM profile found for current user",
            )

        return "PM", pm.pm_id

    @classmethod
    def validate_batch(
        cls,
        db: Session,
        leave_request: LeaveRequest,
        batch: TaskReallocationBatchIn,
        actor_role: str,
        actor_id: Optional[int],
        today: date,
    ) -> tuple[List[dict], List[str]]:
        """
        Phase 1: Validate EVERY action in the batch without mutating tasks or database state.
        Raises ReallocationValidationError or HTTPException on any failure.
        Returns a list of validated action contexts and collected warnings.
        """
        warnings: List[str] = []
        validated_actions: List[dict] = []

        for action in batch.actions:
            task_id = action.task_id

            # 1. Task must exist (404)
            task = TaskRepository.get_task_by_id(db, task_id)
            if not task:
                raise ReallocationValidationError(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found",
                    task_id=task_id,
                )

            # PM project authorization: PM must manage the project of EVERY task in batch
            if actor_role == "PM":
                if not scope.pm_manages_project(db, actor_id, task.project_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access forbidden: You do not manage the project for task {task_id}",
                    )

            # 2. assigned_to must equal the leave applicant
            if task.assigned_to != leave_request.emp_id:
                raise ReallocationValidationError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task not assigned to leave applicant",
                    task_id=task_id,
                )

            # 3. Task status must not be DONE
            task_status_val = (
                task.status.value if hasattr(task.status, "value") else str(task.status)
            ).upper()
            if task.status == TaskStatus.DONE or task_status_val == "DONE":
                raise ReallocationValidationError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task is already completed",
                    task_id=task_id,
                )

            if action.action_type == TaskReallocationActionType.REASSIGN:
                # New assignee must not be the leave applicant
                if action.new_assignee_id == leave_request.emp_id:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot reassign task to the leave applicant",
                        task_id=task_id,
                    )

                new_assignee = TaskRepository.get_employee_by_id(db, action.new_assignee_id)
                if not new_assignee:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Employee with ID {action.new_assignee_id} not found",
                        task_id=task_id,
                    )

                if new_assignee.status != CommonStatus.ACTIVE or not TaskRepository.is_employee_eligible_assignee(
                    db, emp_id=new_assignee.emp_id, task=task
                ):
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Assignee not in team",
                        task_id=task_id,
                    )

                # Overlapping approved leave check
                overlapping_leave = (
                    db.query(LeaveRequest)
                    .filter(
                        LeaveRequest.emp_id == new_assignee.emp_id,
                        LeaveRequest.status == LeaveStatus.APPROVED,
                        LeaveRequest.start_date <= leave_request.end_date,
                        LeaveRequest.end_date >= leave_request.start_date,
                    )
                    .first()
                )
                if overlapping_leave is not None:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Assignee is on leave during this period",
                        task_id=task_id,
                    )

                validated_actions.append({
                    "action": action,
                    "task": task,
                    "new_assignee": new_assignee,
                })

            elif action.action_type == TaskReallocationActionType.EXTEND_DEADLINE:
                # Existing task.due_date must not be null
                if task.due_date is None:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Task has no current due date",
                        task_id=task_id,
                    )

                # new_due_date must be strictly later than current due date
                if action.new_due_date <= task.due_date:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="New due date must be after current due date",
                        task_id=task_id,
                    )

                # new_due_date must be >= today
                if action.new_due_date < today:
                    raise ReallocationValidationError(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="New due date cannot be in the past",
                        task_id=task_id,
                    )

                # Warning: date inside leave window
                if leave_request.start_date <= action.new_due_date <= leave_request.end_date:
                    warnings.append(
                        f"Task {task.task_id}: Extended deadline {action.new_due_date} falls within the leave period ({leave_request.start_date} to {leave_request.end_date})"
                    )

                # Warning: date after milestone target_date
                if task.milestone_id is not None:
                    milestone = TaskRepository.get_milestone_by_id(db, task.milestone_id)
                    if milestone and milestone.target_date and action.new_due_date > milestone.target_date:
                        warnings.append(
                            f"Task {task.task_id}: Extended deadline {action.new_due_date} exceeds milestone target date ({milestone.target_date})"
                        )

                validated_actions.append({
                    "action": action,
                    "task": task,
                })

        return validated_actions, warnings

    @classmethod
    def reallocate_tasks(
        cls,
        db: Session,
        leave_id: int,
        batch: TaskReallocationBatchIn,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
        today: Optional[date] = None,
    ) -> TaskReallocationBatchOut:
        """
        Main entry point for batch task reallocation.
        Validates leave request, authorizes actor, and validates all actions (Phase 1).
        """
        if today is None:
            today = date.today()

        # 1. Leave request exists
        leave_request = LeaveRepository.get_leave_request_by_id(db, leave_id)
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave request with ID {leave_id} not found",
            )

        # 2. Authorize caller
        actor_role, actor_id = cls.authorize_actor(db, current_user, leave_request)

        # 3. Status validation: Only PENDING and APPROVED leave requests are eligible
        if leave_request.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave request is not active",
            )

        # 4. Phase 1: Validate EVERY action
        validated_actions, warnings = cls.validate_batch(
            db=db,
            leave_request=leave_request,
            batch=batch,
            actor_role=actor_role,
            actor_id=actor_id,
            today=today,
        )

        # 5. Phase 2: Apply all modifications in ONE database transaction
        reassigned_out: List[ReassignedTaskOut] = []
        extended_out: List[ExtendedDeadlineTaskOut] = []

        try:
            for item in validated_actions:
                action = item["action"]
                task = item["task"]

                if action.action_type == TaskReallocationActionType.REASSIGN:
                    new_assignee = item["new_assignee"]
                    from_emp_id = task.assigned_to

                    TaskService._apply_reassignment(
                        db=db,
                        task=task,
                        new_assignee=new_assignee,
                        reason=action.reason,
                        actor=current_user,
                        ip=ip_address,
                        commit=False,
                        extra_audit_data={
                            "leave_id": leave_id,
                            "action_type": "REASSIGN",
                        },
                    )
                    reassigned_out.append(
                        ReassignedTaskOut(
                            task_id=task.task_id,
                            from_emp_id=from_emp_id,
                            to_emp_id=new_assignee.emp_id,
                        )
                    )

                elif action.action_type == TaskReallocationActionType.EXTEND_DEADLINE:
                    old_due = task.due_date
                    task.due_date = action.new_due_date
                    task.overdue_notified_at = None
                    db.flush()

                    account_id = getattr(current_user, "account_id", None)
                    write_audit_log(
                        db=db,
                        action=AuditAction.UPDATE,
                        entity_name="TASK",
                        entity_ref_id=str(task.task_id),
                        account_id=account_id,
                        old_value={"due_date": str(old_due)},
                        new_value={
                            "due_date": str(action.new_due_date),
                            "leave_id": leave_id,
                            "action_type": "EXTEND_DEADLINE",
                            "reason": action.reason,
                        },
                        ip_address=ip_address,
                        commit=False,
                    )

                    if task.assigned_to:
                        current_assignee = TaskRepository.get_employee_by_id(db, emp_id=task.assigned_to)
                        if current_assignee and current_assignee.account_id:
                            NotificationService.create_notification(
                                db=db,
                                user_id=current_assignee.account_id,
                                type=TASK_DEADLINE_EXTENDED,
                                title="Task Deadline Extended",
                                message=f"Deadline for task #{task.task_id} ('{task.title}') has been extended to {action.new_due_date}.",
                                link=f"/tasks/{task.task_id}",
                            )

                    extended_out.append(
                        ExtendedDeadlineTaskOut(
                            task_id=task.task_id,
                            old_due_date=old_due,
                            new_due_date=action.new_due_date,
                        )
                    )

            db.commit()

        except Exception:
            db.rollback()
            raise

        return TaskReallocationBatchOut(
            leave_id=leave_id,
            reallocated_count=len(reassigned_out) + len(extended_out),
            reassigned=reassigned_out,
            extended=extended_out,
            warnings=warnings,
        )
