import os
import uuid
import re
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.notifications.service import NotificationService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import TaskProgressStatus, TaskProgressUpdateSchema
from app.models.audit_log import AuditAction
from app.models.employee import Employee
from app.models.enums import TaskStatus, UserType
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

ALLOWED_EXTENSIONS = {".pdf", ".zip", ".tar.gz", ".png", ".jpg", ".jpeg", ".docx"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
UPLOAD_STORAGE_DIR = os.path.join("uploads", "task_submissions")


class TaskSubmissionService:
    """Service layer handling task deliverables submission, validation, and lifecycle transitions."""

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

        # Read content bytes
        if file_bytes is None and file is not None:
            file_bytes = file.file.read()

        file_size = len(file_bytes) if file_bytes else 0
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds the 25MB limit. Current size: {file_size} bytes",
            )

        # Ensure upload storage directory exists
        os.makedirs(UPLOAD_STORAGE_DIR, exist_ok=True)

        # Sanitize filename
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
        """
        Notify Team Lead or Project Manager when a task deliverable is submitted for review.
        Searches team membership, project team, or task creator to resolve lead account UUID.
        """
        lead_account_id = None

        # 1. Look for Team Lead of the submitter's team
        lead_emp = (
            db.query(Employee)
            .join(Team, Team.lead_emp_id == Employee.emp_id)
            .join(TeamMember, TeamMember.team_id == Team.team_id)
            .filter(TeamMember.emp_id == submitter.emp_id)
            .first()
        )
        if lead_emp and lead_emp.account_id:
            lead_account_id = lead_emp.account_id

        # 2. Check team associated with task project
        if not lead_account_id and task.project_id:
            project_team_lead = (
                db.query(Employee)
                .join(Team, Team.lead_emp_id == Employee.emp_id)
                .filter(Team.project_id == task.project_id)
                .first()
            )
            if project_team_lead and project_team_lead.account_id:
                lead_account_id = project_team_lead.account_id

        # 3. Fallback to task creator (if creator != submitter)
        if not lead_account_id and task.created_by and task.created_by != submitter.emp_id:
            creator_emp = db.query(Employee).filter(Employee.emp_id == task.created_by).first()
            if creator_emp and creator_emp.account_id:
                lead_account_id = creator_emp.account_id

        # Dispatch notification if a recipient account is identified
        if lead_account_id:
            try:
                NotificationService.create_notification(
                    db=db,
                    user_id=lead_account_id,
                    type="TASK_SUBMITTED",
                    title="Task Submitted for Review",
                    message=f"Task #{task.task_id} '{task.title}' has been submitted for review by {submitter.full_name}.",
                    link=f"/tasks/{task.task_id}",
                )
            except Exception:
                # Notifications should not abort the submission transaction
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
        file_name: Optional[str] = None,
        file_url: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> TaskSubmission:
        """
        Submit a completed task for review (US-11).
        Transitions status from IN_PROGRESS to IN_REVIEW and triggers audit + notification.
        """
        if not remarks or not remarks.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Remarks are required when submitting a task for review.",
            )

        # 1. Fetch Task
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        # 2. Fetch authenticated employee
        employee = db.query(Employee).filter(Employee.account_id == current_user.account_id).first()
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee record not found for the authenticated user.",
            )

        # 3. Scope Check: Only assigned employee can submit
        if task.assigned_to != employee.emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only the employee assigned to this task can submit it.",
            )

        # 4. Status Validation: Must be IN_PROGRESS
        if task.status != TaskStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit task with status '{task.status.value}'. Task status must be 'IN_PROGRESS'.",
            )

        # 5. Handle file storage & validation
        saved_url, saved_name, saved_size = cls._validate_and_save_file(
            file=file,
            file_bytes=file_bytes,
            original_filename=file_name,
            task_id=task_id,
        )

        final_file_url = saved_url or file_url
        final_file_name = saved_name or file_name
        final_file_size = saved_size or file_size_bytes

        # 6. Insert TaskSubmission record
        submission = TaskSubmission(
            task_id=task.task_id,
            submitted_by=employee.emp_id,
            remarks=remarks.strip(),
            file_url=final_file_url,
            file_name=final_file_name,
            file_size_bytes=final_file_size,
        )
        db.add(submission)

        # 7. Transition task status to IN_REVIEW
        old_status = task.status.value
        task.status = TaskStatus.IN_REVIEW
        db.flush()

        # 8. Dispatch notification to Team Lead
        cls._notify_team_lead(db=db, task=task, submitter=employee)

        # 9. Write audit log
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
        """
        Retrieve chronological list of submissions for a given task (US-11).
        Enforces ordinary employee isolation: employees may only inspect submissions for their own tasks.
        """
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        # Role scope check: Ordinary employees can only view submissions of tasks assigned to them
        if current_user.user_type == UserType.EMPLOYEE:
            employee = db.query(Employee).filter(Employee.account_id == current_user.account_id).first()
            if not employee:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Employee record not found for the authenticated user.",
                )

            # Check if user is the assigned employee
            is_assigned = (task.assigned_to == employee.emp_id)

            # Check if user is the team lead for this task
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
        """
        Update the progress status, percentage, and blocker information of an active task (US-10).

        Business Rules:
        - Permitted statuses: IN_PROGRESS, BLOCKED.
        - progress_pct must be between 0 and 99 (100% requires submission via review flow, returning 400).
        - If status == BLOCKED, blocker_reason is required (min 5 characters), returning 422 if missing.
        - If status moves back to IN_PROGRESS, blocker_reason is cleared.
        - Only assigned employee or Team Lead of that team may update progress, returning 403 otherwise.
        - Auto-triggers TASK_BLOCKED notification to the Team Lead when flagged BLOCKED.
        - Records structured audit log for audit compliance.
        """
        # 1. Fetch Task
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found.",
            )

        # 2. Fetch authenticated employee
        employee = TaskRepository.get_employee_by_account_id(db, current_user.account_id)
        is_admin = current_user.user_type in [UserType.ADMIN, UserType.SYSTEM_ADMIN]

        if not employee and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for the authenticated user.",
            )

        # 3. Scope Check: Assigned employee, Team Lead of that team, or Admin
        is_assigned = (task.assigned_to == employee.emp_id) if employee else False
        is_lead = TaskRepository.is_team_lead_for_task(db, employee.emp_id, task) if employee else False

        if not is_assigned and not is_lead and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only the assigned employee or the Team Lead can update task progress.",
            )

        # 4. Progress Percentage Validation
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

        # 5. Status & Blocker Reason Validation
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

        # 6. Capture pre-update state for audit log
        old_status = task.status.value if task.status else None
        old_progress = getattr(task, "progress_pct", 0)
        old_blocker = getattr(task, "blocker_reason", None)

        # 7. Apply updates to task
        task.status = target_status
        task.progress_pct = payload.progress_pct
        task.blocker_reason = target_blocker_reason
        db.flush()

        # 8. Notification Hook: When flagged BLOCKED, notify Team Lead
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
                    # Notifications should not abort progress update transaction
                    pass

        # 9. Record Audit Log
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

