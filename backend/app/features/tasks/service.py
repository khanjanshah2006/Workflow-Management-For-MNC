import os
import uuid
import re
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.notifications.service import NotificationService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import TaskAssignRequest, TaskReassignRequest, TaskResponse
from app.models.audit_log import AuditAction
from app.models.employee import Employee
from app.models.enums import TaskStatus, UserType
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

ALLOWED_EXTENSIONS = {".pdf", ".zip", ".tar.gz", ".png", ".jpg", ".jpeg", ".docx"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
UPLOAD_STORAGE_DIR = os.path.join("uploads", "task_submissions")


# ==========================================
# Task Exceptions (US-09, US-14)
# ==========================================

class TaskNotFoundError(Exception):
    pass


class AssigneeNotFoundError(Exception):
    pass


class AssigneeNotEligibleError(Exception):
    pass


class TaskAssignmentForbiddenError(Exception):
    pass


class SameAssigneeError(Exception):
    pass


class InvalidReassignmentReasonError(Exception):
    pass


# ==========================================
# Task Management Service (US-09, US-14)
# ==========================================

class TaskService:
    """Business logic for task assignment and reassignment management (US-09, US-14)."""

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

    @staticmethod
    def reassign_task(
        db: Session,
        task_id: int,
        payload: TaskReassignRequest,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> TaskResponse:
        """
        Reassign an active task to another team member (US-14).
        Enforces distinct assignee (new != old), reason min length (10 chars),
        team eligibility, audit logging, and dual notifications to previous & new assignees.
        """
        # 1. Fetch task
        task = TaskRepository.get_task_by_id(db, task_id=task_id)
        if not task:
            raise TaskNotFoundError(f"Task with ID {task_id} not found.")

        # 2. Authorize caller
        TaskService.check_can_manage_task(db, current_user=current_user, task=task)

        # 3. Validate reason length (min 10 characters)
        clean_reason = payload.reason.strip() if payload.reason else ""
        if len(clean_reason) < 10:
            raise InvalidReassignmentReasonError("Reassignment reason must be at least 10 characters.")

        # 4. Enforce new assignee differs from current assignee
        if task.assigned_to == payload.new_assignee_id:
            raise SameAssigneeError("Cannot reassign task to the current assignee.")

        # 5. Fetch target new assignee
        new_assignee = TaskRepository.get_employee_by_id(db, emp_id=payload.new_assignee_id)
        if not new_assignee:
            raise AssigneeNotFoundError(f"Employee with ID {payload.new_assignee_id} not found.")

        # 6. Verify eligibility in team/project roster
        if not TaskRepository.is_employee_eligible_assignee(db, emp_id=new_assignee.emp_id, task=task):
            raise AssigneeNotEligibleError(
                f"Employee with ID {payload.new_assignee_id} is not an active member of the task team."
            )

        previous_assignee_id = task.assigned_to
        previous_assignee = (
            TaskRepository.get_employee_by_id(db, emp_id=previous_assignee_id)
            if previous_assignee_id
            else None
        )

        # 7. Persist reassignment
        updated_task = TaskRepository.reassign_task(
            db, task=task, new_assignee_id=new_assignee.emp_id
        )

        # 8. Record structured audit log entry
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="TASK",
            entity_ref_id=str(task.task_id),
            account_id=current_user.account_id,
            old_value={"assigned_to": previous_assignee_id},
            new_value={"assigned_to": new_assignee.emp_id, "reason": clean_reason},
            ip_address=ip_address,
        )

        # 9. Dual notification hooks
        # A. Notification for the new assignee
        if new_assignee.account_id:
            NotificationService.create_notification(
                db=db,
                user_id=new_assignee.account_id,
                type="TASK_ASSIGNED",
                title="New Task Assigned",
                message=f"You have been assigned to task #{task.task_id}: '{task.title}'",
                link=f"/tasks/{task.task_id}",
            )

        # B. Notification for the previous assignee (if exists)
        if previous_assignee and previous_assignee.account_id:
            NotificationService.create_notification(
                db=db,
                user_id=previous_assignee.account_id,
                type="TASK_REASSIGNED",
                title="Task Reassigned",
                message=f"Task #{task.task_id} ('{task.title}') has been reassigned to another team member. Reason: {clean_reason}",
                link=f"/tasks/{task.task_id}",
            )

        db.commit()
        return TaskResponse.model_validate(updated_task)


# ==========================================
# Task Submission Service (US-11)
# ==========================================

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

        # Dispatch notification if lead account resolved
        if lead_account_id:
            NotificationService.create_notification(
                db=db,
                user_id=lead_account_id,
                type="TASK_SUBMITTED",
                title="Task Submitted for Review",
                message=f"Employee {submitter.full_name} submitted task #{task.task_id} ('{task.title}') for review.",
                link=f"/tasks/{task.task_id}/review",
            )

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
        Submit a task for review (US-11).
        Transitions task status from IN_PROGRESS to IN_REVIEW, validates deliverables,
        stores attachment, notifies the Team Lead, and logs audit record.
        """
        if not remarks or not remarks.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Remarks are required when submitting a task.",
            )

        # 1. Fetch task
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
