import logging
from typing import Any, List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import (
    TaskResubmitResponse,
    TaskResubmitSchema,
    TaskReviewQueueItem,
)
from app.models.enums import AuditAction, TaskStatus, UserType
from app.models.employee import Employee
from app.models.team import Team

logger = logging.getLogger(__name__)


class TaskService:
    """Business logic for Task review queue triage and resubmission (US-13)."""

    @classmethod
    def _resolve_employee_and_team(
        cls, db: Session, user: Any
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Resolves (emp_id, team_id) from the current_user context.
        Supports mock user objects with direct attributes as well as database-backed UserAccount entities.
        """
        emp_id = getattr(user, "emp_id", None)
        team_id = getattr(user, "team_id", None)

        account_id = getattr(user, "account_id", None)
        if emp_id is None and account_id is not None:
            if isinstance(account_id, str):
                try:
                    account_id = UUID(account_id)
                except ValueError:
                    pass
            emp = TaskRepository.get_employee_by_account_id(db, account_id)
            if emp is not None:
                emp_id = emp.emp_id

        if team_id is None and emp_id is not None:
            team = TaskRepository.get_team_for_employee(db, emp_id)
            if team is not None:
                team_id = team.team_id

        return emp_id, team_id

    @classmethod
    def get_review_queue(
        cls,
        db: Session,
        current_user: Any,
        priority: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> List[TaskReviewQueueItem]:
        """
        Retrieve tasks in IN_REVIEW status scoped to the Team Lead's team (US-13).
        Scope Check: task.team_id == current_user.team_id and task.status == TaskStatus.IN_REVIEW.
        """
        emp_id, team_id = cls._resolve_employee_and_team(db, current_user)

        user_type_raw = getattr(current_user, "user_type", None)
        user_type = (
            user_type_raw.value if hasattr(user_type_raw, "value") else str(user_type_raw)
        )

        # Scoping rule:
        # If team_id is identified, filter strictly by team_id.
        # If current_user is ADMIN or PM without a specific team_id, return tasks (or [] if team_id explicitly required).
        # Per AC: "GET /review-queue returns only tasks with status == 'IN_REVIEW' belonging to the TL's team."
        target_team_id = team_id

        raw_results = TaskRepository.get_review_queue(
            db=db,
            team_id=target_team_id,
            priority=priority,
            page=page,
            limit=limit,
        )

        queue_items: List[TaskReviewQueueItem] = []
        for task, employee, submission in raw_results:
            queue_items.append(
                TaskReviewQueueItem(
                    task_id=task.task_id,
                    title=task.title,
                    description=task.description,
                    priority=task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                    status=task.status.value if hasattr(task.status, "value") else str(task.status),
                    team_id=task.team_id,
                    project_id=task.project_id,
                    milestone_id=task.milestone_id,
                    assigned_to=task.assigned_to,
                    assignee_name=employee.full_name if employee else None,
                    submission_remarks=submission.remarks if submission else None,
                    deliverable_file_url=submission.file_url if submission else None,
                    submission_timestamp=submission.created_at if submission else None,
                    created_at=task.created_at,
                    due_date=task.due_date,
                )
            )

        return queue_items

    @classmethod
    def resubmit_task(
        cls,
        db: Session,
        task_id: int,
        payload: TaskResubmitSchema,
        current_user: Any,
    ) -> TaskResubmitResponse:
        """
        Resubmit revised work following task rejection (US-13).
        - Scope Check: task.assigned_to == current_user.emp_id.
        - Validation: Task must currently have status == TaskStatus.REJECTED; otherwise 400 Bad Request.
        - Business Logic:
          1. Update task.status = TaskStatus.IN_REVIEW.
          2. Create new record in task_submission.
          3. Notify Team Lead: "TASK_RESUBMITTED".
          4. Record audit log.
        """
        task = TaskRepository.get_task_by_id(db, task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found",
            )

        emp_id, _ = cls._resolve_employee_and_team(db, current_user)

        # 1. Scope Check: task.assigned_to == current_user.emp_id
        if task.assigned_to is None or emp_id is None or task.assigned_to != emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You can only resubmit tasks assigned to you.",
            )

        # 2. Validation: Task must currently have status == TaskStatus.REJECTED
        current_task_status = (
            task.status.value if hasattr(task.status, "value") else str(task.status)
        )
        if current_task_status != TaskStatus.REJECTED.value and current_task_status != "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task must currently have status == 'REJECTED' to resubmit. Current status: '{current_task_status}'.",
            )

        # 3. Update task.status = TaskStatus.IN_REVIEW
        TaskRepository.update_task_status(db, task, TaskStatus.IN_REVIEW)

        # 4. Create new record in task_submission
        submission = TaskRepository.create_submission(
            db=db,
            task_id=task.task_id,
            submitted_by=emp_id,
            remarks=payload.revised_remarks,
            file_url=payload.new_file_url,
        )

        # 5. Notify Team Lead: "TASK_RESUBMITTED"
        cls._notify_team_lead(db, task)

        # 6. Audit log
        user_account_id = getattr(current_user, "account_id", None)
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=user_account_id,
            old_value={"status": current_task_status},
            new_value={
                "status": TaskStatus.IN_REVIEW.value,
                "submission_id": submission.submission_id,
                "revised_remarks": payload.revised_remarks,
                "new_file_url": payload.new_file_url,
            },
        )

        # 7. Commit atomic transaction
        db.commit()
        db.refresh(task)
        db.refresh(submission)

        return TaskResubmitResponse(
            task_id=task.task_id,
            title=task.title,
            status=task.status.value if hasattr(task.status, "value") else str(task.status),
            team_id=task.team_id,
            assigned_to=task.assigned_to,
            submission_id=submission.submission_id,
            revised_remarks=submission.remarks,
            new_file_url=submission.file_url,
            message="Task resubmitted successfully",
        )

    @classmethod
    def _notify_team_lead(cls, db: Session, task: Any) -> None:
        """Helper to send 'TASK_RESUBMITTED' notification to the relevant Team Lead."""
        try:
            lead_emp: Optional[Employee] = None

            # First priority: check team directly assigned to task
            if task.team_id:
                lead_emp = TaskRepository.get_team_lead_employee(db, task.team_id)

            # Second priority: check team of assigned employee
            if lead_emp is None and task.assigned_to:
                team = TaskRepository.get_team_for_employee(db, task.assigned_to)
                if team and team.lead_emp_id:
                    lead_emp = TaskRepository.get_employee_by_id(db, team.lead_emp_id)

            if lead_emp and lead_emp.account_id:
                from app.features.notifications.service import NotificationService

                NotificationService.create_notification(
                    db=db,
                    user_id=lead_emp.account_id,
                    type="TASK_RESUBMITTED",
                    title="Task Resubmitted",
                    message=f"Task #{task.task_id} '{task.title}' has been resubmitted for review.",
                    link=f"/api/v1/tasks/{task.task_id}",
                )
        except Exception as exc:
            logger.warning(f"Could not dispatch TASK_RESUBMITTED notification: {exc}")
