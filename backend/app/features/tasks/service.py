import logging
import os
import re
import uuid
from typing import Any, List, Optional, Tuple
from uuid import UUID
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.notifications.service import NotificationService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import (
    ReviewDecision,
    TaskCreate,
    TaskProgressStatus,
    TaskProgressUpdateSchema,
    TaskResubmitResponse,
    TaskResubmitSchema,
    TaskReviewDecisionSchema,
    TaskReviewQueueItem,
    TaskReviewResponse,
)
from app.models.audit_log import AuditAction
from app.models.employee import Employee
from app.models.enums import MilestoneStatus, PriorityLevel, TaskStatus, UserType
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".zip", ".tar.gz", ".png", ".jpg", ".jpeg", ".docx"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
UPLOAD_STORAGE_DIR = os.path.join("uploads", "task_submissions")


class TaskSubmissionService:
    """Service layer handling task deliverables submission, validation, and lifecycle transitions (US-11)."""

    @staticmethod
    def is_allowed_filename(filename: str) -> bool:
        """Check if filename ends with one of the permitted deliverable file extensions."""
        fn_lower = filename.lower()
        if fn_lower.endswith(".tar.gz"):
            return True
        _, ext = os.path.splitext(fn_lower)
        return ext in ALLOWED_EXTENSIONS

    @classmethod
    def _validate_and_save_file(
        cls,
        file: Optional[UploadFile] = None,
        file_bytes: Optional[bytes] = None,
        original_filename: Optional[str] = None,
        task_id: int = 0,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Validate uploaded deliverable extension and size, then persist to local storage."""
        if not file and not file_bytes:
            return None, None, None

        filename = original_filename or (file.filename if file else "deliverable")
        if not cls.is_allowed_filename(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File type not allowed. Allowed types: .pdf, .zip, .tar.gz, .png, .jpg, .docx",
            )

        if file_bytes is None and file is not None:
            file_bytes = file.file.read()

        file_size = len(file_bytes) if file_bytes else 0
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds the 25MB limit. Current size: {file_size} bytes",
            )

        os.makedirs(UPLOAD_STORAGE_DIR, exist_ok=True)

        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(filename))
        stored_filename = f"task_{task_id}_{uuid.uuid4().hex[:10]}_{safe_filename}"
        storage_path = os.path.join(UPLOAD_STORAGE_DIR, stored_filename)

        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        file_url = f"/uploads/task_submissions/{stored_filename}"
        return file_url, filename, file_size

    @classmethod
    def _notify_team_lead(
        cls,
        db: Session,
        task: Task,
        submitter: Employee,
    ) -> None:
        lead_account_id = None

        lead_emp = (
            db.query(Employee)
            .join(Team, Team.lead_emp_id == Employee.emp_id)
            .join(TeamMember, TeamMember.team_id == Team.team_id)
            .filter(TeamMember.emp_id == submitter.emp_id)
            .first()
        )
        if lead_emp and lead_emp.account_id:
            lead_account_id = lead_emp.account_id

        if not lead_account_id and task.project_id:
            project_team_lead = (
                db.query(Employee)
                .join(Team, Team.lead_emp_id == Employee.emp_id)
                .filter(Team.project_id == task.project_id)
                .first()
            )
            if project_team_lead and project_team_lead.account_id:
                lead_account_id = project_team_lead.account_id

        if not lead_account_id and task.created_by and task.created_by != submitter.emp_id:
            creator_emp = db.query(Employee).filter(Employee.emp_id == task.created_by).first()
            if creator_emp and creator_emp.account_id:
                lead_account_id = creator_emp.account_id

        if lead_account_id:
            try:
                NotificationService.create_notification(
                    db=db,
                    user_id=lead_account_id,
                    type="TASK_SUBMITTED",
                    title="Task Submitted for Review",
                    message=f"Task #{task.task_id} '{task.title}' has been submitted for review by {submitter.full_name}.",
                    link=f"/api/v1/tasks/{task.task_id}/submissions",
                )
            except Exception:
                pass

    @classmethod
    def submit_task(
        cls,
        db: Session,
        task_id: int,
        remarks: str,
        current_user: UserAccount,
        file: Optional[UploadFile] = None,
        file_bytes: Optional[bytes] = None,
        original_filename: Optional[str] = None,
        pre_existing_file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> TaskSubmission:
        if not remarks or not remarks.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Remarks cannot be empty.",
            )

        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        employee = db.query(Employee).filter(Employee.account_id == current_user.account_id).first()
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee record not found for authenticated user.",
            )

        if task.assigned_to != employee.emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not assigned to this task.",
            )

        current_status = task.status.value if hasattr(task.status, "value") else str(task.status)
        if current_status not in ["TODO", "IN_PROGRESS", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit task currently in '{current_status}' status. Task must be in TODO, IN_PROGRESS, or REJECTED.",
            )

        final_file_url = pre_existing_file_url
        final_file_name = file_name
        final_file_size = file_size_bytes

        if file or file_bytes:
            saved_url, saved_name, saved_size = cls._validate_and_save_file(
                file=file,
                file_bytes=file_bytes,
                original_filename=original_filename,
                task_id=task_id,
            )
            final_file_url = saved_url
            final_file_name = saved_name
            final_file_size = saved_size

        old_status = current_status
        task.status = TaskStatus.IN_REVIEW
        db.flush()

        submission = TaskSubmission(
            task_id=task_id,
            submitted_by=employee.emp_id,
            remarks=remarks.strip(),
            file_url=final_file_url,
            file_name=final_file_name,
            file_size_bytes=final_file_size,
        )
        db.add(submission)
        db.flush()

        cls._notify_team_lead(db, task, employee)

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=current_user.account_id,
            old_value={"status": old_status},
            new_value={
                "status": TaskStatus.IN_REVIEW.value,
                "submission_id": submission.submission_id,
                "file_name": final_file_name,
            },
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(submission)
        return submission

    @classmethod
    def get_task_submissions(
        cls,
        db: Session,
        task_id: int,
        current_user: UserAccount,
    ) -> List[TaskSubmission]:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        if current_user.user_type == UserType.EMPLOYEE:
            employee = db.query(Employee).filter(Employee.account_id == current_user.account_id).first()
            if not employee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee record not found for the authenticated user.",
                )

            is_assigned = (task.assigned_to == employee.emp_id)
            is_team_lead = (
                db.query(Team)
                .filter(Team.project_id == task.project_id, Team.lead_emp_id == employee.emp_id)
                .first()
                is not None
            )

            if not is_assigned and not is_team_lead:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have permission to view submissions for this task.",
                )

        submissions = (
            db.query(TaskSubmission)
            .filter(TaskSubmission.task_id == task_id)
            .order_by(TaskSubmission.submitted_at.asc(), TaskSubmission.submission_id.asc())
            .all()
        )
        return submissions


class TaskService:
    """Service layer handling Task CRUD, review queue triage, and resubmission (US-09, US-13, US-32)."""

    # ── US-13 Review Queue & Resubmission Helpers ────────────────────────

    @classmethod
    def _resolve_employee_and_team(
        cls, db: Session, user: Any
    ) -> tuple[Optional[int], Optional[int]]:
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
        emp_id, team_id = cls._resolve_employee_and_team(db, current_user)
        raw_results = TaskRepository.get_review_queue(
            db=db,
            team_id=team_id,
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
                    submission_timestamp=submission.submitted_at if submission else None,
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
        task = TaskRepository.get_task_by_id(db, task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found",
            )

        emp_id, _ = cls._resolve_employee_and_team(db, current_user)

        if task.assigned_to is None or emp_id is None or task.assigned_to != emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You can only resubmit tasks assigned to you.",
            )

        current_task_status = (
            task.status.value if hasattr(task.status, "value") else str(task.status)
        )
        if current_task_status != TaskStatus.REJECTED.value and current_task_status != "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task must currently have status == 'REJECTED' to resubmit. Current status: '{current_task_status}'.",
            )

        TaskRepository.update_task_status(db, task, TaskStatus.IN_REVIEW)

        submission = TaskRepository.create_submission(
            db=db,
            task_id=task.task_id,
            submitted_by=emp_id,
            remarks=payload.revised_remarks,
            file_url=payload.new_file_url,
        )

        cls._notify_team_lead(db, task)

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
        try:
            lead_emp: Optional[Employee] = None

            if task.team_id:
                lead_emp = TaskRepository.get_team_lead_employee(db, task.team_id)

            if lead_emp is None and task.assigned_to:
                team = TaskRepository.get_team_for_employee(db, task.assigned_to)
                if team and team.lead_emp_id:
                    lead_emp = TaskRepository.get_employee_by_id(db, team.lead_emp_id)

            if lead_emp and lead_emp.account_id:
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

    # ── US-09 / US-32 Operations ──────────────────────────────────────────

    @staticmethod
    def create_task(
        db: Session,
        payload: TaskCreate,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> Task:
        actor_emp = TaskRepository.get_employee_by_account_id(db, actor.account_id)

        project = TaskRepository.get_project_by_id(db, payload.project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {payload.project_id} not found.",
            )

        team = TaskRepository.get_team_by_id(db, payload.team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team with ID {payload.team_id} not found.",
            )

        is_privileged = actor.user_type in (
            UserType.PM,
            UserType.ADMIN,
            UserType.SYSTEM_ADMIN,
        )
        is_team_lead = (
            actor.user_type == UserType.EMPLOYEE
            and actor_emp is not None
            and team.lead_emp_id == actor_emp.emp_id
        )
        if not is_privileged and not is_team_lead:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only a Team Lead, PM, or Admin can create tasks.",
            )

        if payload.milestone_id is not None:
            milestone = TaskRepository.get_milestone_by_id(db, payload.milestone_id)
            if not milestone:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Milestone with ID {payload.milestone_id} not found.",
                )

        if (
            payload.start_date is not None
            and payload.due_date is not None
            and payload.due_date < payload.start_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="due_date cannot be earlier than start_date.",
            )

        if payload.assigned_to is not None:
            assignee = TaskRepository.get_employee_by_id(db, payload.assigned_to)
            if not assignee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assignee employee with ID {payload.assigned_to} not found.",
                )
            if not TaskRepository.is_active_team_member(
                db, payload.team_id, payload.assigned_to
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assignee is not an active member of the specified team.",
                )

        task = Task(
            project_id=payload.project_id,
            team_id=payload.team_id,
            milestone_id=payload.milestone_id,
            assigned_to=payload.assigned_to,
            created_by=actor_emp.emp_id if actor_emp else None,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            status=TaskStatus.TODO,
            progress_pct=0,
            rejection_count=0,
            start_date=payload.start_date,
            due_date=payload.due_date,
        )
        TaskRepository.create_task(db, task)

        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=actor.account_id,
            new_value={
                "title": task.title,
                "project_id": task.project_id,
                "team_id": task.team_id,
                "assigned_to": task.assigned_to,
                "status": task.status.value,
            },
            ip_address=ip_address,
        )

        db.commit()
        return TaskRepository.get_task_by_id(db, task.task_id) or task

    @staticmethod
    def get_task(db: Session, task_id: int) -> Task:
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )
        return task

    @staticmethod
    def list_my_tasks(
        db: Session,
        actor: UserAccount,
        status_filter: Optional[TaskStatus] = None,
        priority_filter: Optional[PriorityLevel] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Task], int]:
        actor_emp = TaskRepository.get_employee_by_account_id(db, actor.account_id)
        if not actor_emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee record not found for the authenticated user.",
            )
        return TaskRepository.list_my_tasks(
            db=db,
            emp_id=actor_emp.emp_id,
            status=status_filter,
            priority=priority_filter,
            page=page,
            limit=limit,
        )

    @staticmethod
    def list_project_tasks(
        db: Session,
        project_id: int,
        team_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        status_filter: Optional[TaskStatus] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Task], int]:
        project = TaskRepository.get_project_by_id(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found.",
            )
        return TaskRepository.list_project_tasks(
            db=db,
            project_id=project_id,
            team_id=team_id,
            milestone_id=milestone_id,
            status=status_filter,
            page=page,
            limit=limit,
        )


class TaskProgressService:
    """Service layer handling task progress state machine transitions, blocker tracking, and Team Lead alerts (US-10)."""

    @classmethod
    def update_progress(
        cls,
        db: Session,
        task_id: int,
        payload: TaskProgressUpdateSchema,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> Task:
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        employee = TaskRepository.get_employee_by_account_id(db, current_user.account_id)
        is_admin = current_user.user_type in [UserType.ADMIN, UserType.SYSTEM_ADMIN]

        if not employee and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for the authenticated user.",
            )

        is_assigned = (task.assigned_to == employee.emp_id) if employee else False
        is_lead = TaskRepository.is_team_lead_for_task(db, employee.emp_id, task) if employee else False

        if not is_assigned and not is_lead and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only the assigned employee or the Team Lead can update task progress.",
            )

        if payload.progress_pct == 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setting progress to 100% requires submitting the task for review via the /submit flow.",
            )

        if payload.progress_pct < 0 or payload.progress_pct > 99:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Progress percentage must be an integer between 0 and 99.",
            )

        if payload.status == TaskProgressStatus.BLOCKED:
            if not payload.blocker_reason or len(payload.blocker_reason.strip()) < 5:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="blocker_reason is required (minimum 5 characters) when task is flagged as BLOCKED.",
                )
            target_status = TaskStatus.BLOCKED
            target_blocker_reason = payload.blocker_reason.strip()
        elif payload.status == TaskProgressStatus.IN_PROGRESS:
            target_status = TaskStatus.IN_PROGRESS
            target_blocker_reason = None
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{payload.status}'. Permitted values are 'IN_PROGRESS' and 'BLOCKED'.",
            )

        old_status = task.status.value if task.status else None
        old_progress = getattr(task, "progress_pct", 0)
        old_blocker = getattr(task, "blocker_reason", None)

        task.status = target_status
        task.progress_pct = payload.progress_pct
        task.blocker_reason = target_blocker_reason
        db.flush()

        if target_status == TaskStatus.BLOCKED:
            team = TaskRepository.get_team_for_task(db, task)
            lead_emp = TaskRepository.get_team_lead_employee(db, team) if team else None
            if lead_emp and lead_emp.account_id:
                try:
                    NotificationService.create_notification(
                        db=db,
                        user_id=lead_emp.account_id,
                        type="TASK_BLOCKED",
                        title="Task Flagged as Blocked",
                        message=f"Task #{task.task_id} '{task.title}' has been flagged as BLOCKED. Reason: {target_blocker_reason}",
                        link=f"/tasks/{task.task_id}",
                    )
                except Exception:
                    pass

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=current_user.account_id,
            old_value={
                "status": old_status,
                "progress_pct": old_progress,
                "blocker_reason": old_blocker,
            },
            new_value={
                "status": target_status.value,
                "progress_pct": task.progress_pct,
                "blocker_reason": target_blocker_reason,
            },
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(task)
        return task


class TaskReviewService:
    """Service layer handling task review decisions, evaluation state machine, milestone recalculation, and notifications (US-12)."""

    @classmethod
    def review_task(
        cls,
        db: Session,
        task_id: int,
        payload: TaskReviewDecisionSchema,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> TaskReviewResponse:
        """
        Evaluate a submitted task (US-12): approve (completing task and updating milestones)
        or reject (requesting revisions with mandatory feedback).
        """
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        user_type_str = str(
            current_user.user_type.value if hasattr(current_user.user_type, "value") else current_user.user_type
        ).upper()

        is_authorized = False
        if user_type_str in ("ADMIN", "SYSTEM_ADMIN"):
            is_authorized = True
        elif user_type_str in ("PM", "PROJECT_MANAGER"):
            pm = db.query(ProjectManager).filter(ProjectManager.account_id == current_user.account_id).first()
            project = db.query(Project).filter(Project.project_id == task.project_id).first()
            if pm and project and project.pm_id == pm.pm_id:
                is_authorized = True
            elif not pm:
                is_authorized = True
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Only the Project Manager assigned to this project can review this task.",
                )
        elif user_type_str in ("TEAM_LEAD", "EMPLOYEE"):
            emp = db.query(Employee).filter(Employee.account_id == current_user.account_id).first()
            if not emp:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Employee profile not found.",
                )

            # Check if user is the Team Lead of the assigned employee's team
            is_lead_of_assigned_team = False
            if task.assigned_to:
                is_lead_of_assigned_team = (
                    db.query(Team)
                    .join(TeamMember, TeamMember.team_id == Team.team_id)
                    .filter(TeamMember.emp_id == task.assigned_to, Team.lead_emp_id == emp.emp_id)
                    .first()
                    is not None
                )

            # If task.team_id is explicitly set
            is_lead_of_task_team = False
            if getattr(task, "team_id", None):
                is_lead_of_task_team = (
                    db.query(Team)
                    .filter(Team.team_id == task.team_id, Team.lead_emp_id == emp.emp_id)
                    .first()
                    is not None
                )

            # If employee not mapped in TeamMember, fallback to team on the project
            lead_for_project_team = False
            if not is_lead_of_assigned_team and not is_lead_of_task_team and not db.query(TeamMember).filter(TeamMember.emp_id == task.assigned_to).first():
                lead_for_project_team = (
                    db.query(Team)
                    .filter(Team.project_id == task.project_id, Team.lead_emp_id == emp.emp_id)
                    .first()
                    is not None
                )

            if is_lead_of_assigned_team or is_lead_of_task_team or lead_for_project_team:
                is_authorized = True

        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only the Team Lead of that task's team or the Project Manager can review.",
            )

        # Status Check: Must be IN_REVIEW
        if task.status != TaskStatus.IN_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task is not awaiting review.",
            )

        assigned_emp = db.query(Employee).filter(Employee.emp_id == task.assigned_to).first()
        milestone_status_result = None

        if payload.decision == ReviewDecision.APPROVE:
            task.status = TaskStatus.DONE
            task.progress_pct = 100
            task.completed_at = func.now()

            # Recalculate milestone progress: If all tasks in task.milestone_id are DONE, update milestone status
            if task.milestone_id:
                milestone_tasks = db.query(Task).filter(Task.milestone_id == task.milestone_id).all()
                if milestone_tasks and all(t.status == TaskStatus.DONE or t.task_id == task.task_id for t in milestone_tasks):
                    milestone = db.query(ProjectMilestone).filter(ProjectMilestone.id == task.milestone_id).first()
                    if milestone:
                        milestone.status = MilestoneStatus.COMPLETED
                        milestone.completed_at = func.now()
                        milestone_status_result = MilestoneStatus.COMPLETED.value
                else:
                    milestone = db.query(ProjectMilestone).filter(ProjectMilestone.id == task.milestone_id).first()
                    if milestone:
                        milestone_status_result = milestone.status.value if hasattr(milestone.status, "value") else str(milestone.status)

            if assigned_emp and assigned_emp.account_id:
                try:
                    NotificationService.create_notification(
                        db=db,
                        user_id=assigned_emp.account_id,
                        type="TASK_APPROVED",
                        title="Task Approved",
                        message=f"Task #{task.task_id} '{task.title}' has been approved.",
                        link=f"/tasks/{task.task_id}",
                    )
                except Exception:
                    pass

            write_audit_log(
                db=db,
                action=AuditAction.APPROVE,
                entity_name="TASK",
                entity_ref_id=str(task.task_id),
                account_id=current_user.account_id,
                old_value={"status": "IN_REVIEW"},
                new_value={"status": "DONE", "progress_pct": 100},
                ip_address=ip_address,
            )

            message = f"Task #{task.task_id} successfully approved and marked as DONE."

        else:  # REJECT
            if not payload.feedback or len(payload.feedback.strip()) < 10:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Feedback is mandatory (minimum 10 characters) when rejecting a task.",
                )

            task.status = TaskStatus.REJECTED
            task.rejection_feedback = payload.feedback.strip()
            task.rejection_count = (task.rejection_count or 0) + 1

            if task.milestone_id:
                milestone = db.query(ProjectMilestone).filter(ProjectMilestone.id == task.milestone_id).first()
                if milestone:
                    if milestone.status == MilestoneStatus.COMPLETED:
                        milestone.status = MilestoneStatus.PENDING
                        milestone.completed_at = None
                    milestone_status_result = milestone.status.value if hasattr(milestone.status, "value") else str(milestone.status)

            if assigned_emp and assigned_emp.account_id:
                try:
                    NotificationService.create_notification(
                        db=db,
                        user_id=assigned_emp.account_id,
                        type="TASK_REJECTED",
                        title="Task Rejected - Revision Requested",
                        message=f"Task #{task.task_id} '{task.title}' was rejected. Feedback: {payload.feedback.strip()}",
                        link=f"/tasks/{task.task_id}",
                    )
                except Exception:
                    pass

            write_audit_log(
                db=db,
                action=AuditAction.UPDATE,
                entity_name="TASK",
                entity_ref_id=str(task.task_id),
                account_id=current_user.account_id,
                old_value={"status": "IN_REVIEW"},
                new_value={
                    "status": "REJECTED",
                    "rejection_feedback": payload.feedback.strip(),
                    "rejection_count": task.rejection_count,
                },
                ip_address=ip_address,
            )

            message = f"Task #{task.task_id} rejected with revision feedback."

        db.commit()
        db.refresh(task)

        return TaskReviewResponse(
            task_id=task.task_id,
            status=task.status.value if hasattr(task.status, "value") else str(task.status),
            progress_pct=task.progress_pct or 0,
            completed_at=task.completed_at,
            rejection_feedback=task.rejection_feedback,
            rejection_count=task.rejection_count or 0,
            milestone_id=task.milestone_id,
            milestone_status=milestone_status_result,
            message=message,
        )


# Add method to TaskSubmissionService as well for backward compatibility
TaskSubmissionService.review_task = TaskReviewService.review_task

