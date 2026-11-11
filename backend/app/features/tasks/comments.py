from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.features.notifications.service import NotificationService
from app.features.tasks.schemas import TaskCommentResponse
from app.models.employee import Employee
from app.models.enums import UserType
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task, TaskComment
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


class TaskCommentService:
    """Task thread persistence, project scope checks, and counterpart notifications."""

    @staticmethod
    def _task_or_404(db: Session, task_id: int) -> Task:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        return task

    @staticmethod
    def _identity(db: Session, user: UserAccount, task: Task) -> Tuple[Optional[Employee], str, str, bool, bool]:
        """Return employee, display name, role badge, is project PM, is team lead."""
        role = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        employee = db.query(Employee).filter(Employee.account_id == user.account_id).first()
        if employee is not None:
            is_team_lead = db.query(Team).filter(
                Team.project_id == task.project_id,
                Team.lead_emp_id == employee.emp_id,
            ).first() is not None
            return employee, employee.full_name, "TEAM_LEAD" if is_team_lead else role, False, is_team_lead

        if user.user_type == UserType.PM:
            pm = db.query(ProjectManager).filter(ProjectManager.account_id == user.account_id).first()
            if pm is not None:
                return None, pm.full_name, "PM", True, False
        return None, user.email, role, False, False

    @classmethod
    def _authorize_scope(cls, db: Session, task: Task, user: UserAccount) -> Tuple[Optional[Employee], str, str, bool, bool]:
        identity = cls._identity(db, user, task)
        employee, _, _, is_pm, is_team_lead = identity
        role = user.user_type

        if role in (UserType.ADMIN, UserType.SYSTEM_ADMIN):
            return identity

        if role == UserType.PM:
            project_pm = db.query(Project).filter(
                Project.project_id == task.project_id,
                Project.pm_id == db.query(ProjectManager.pm_id).filter(
                    ProjectManager.account_id == user.account_id
                ).scalar_subquery(),
            ).first()
            if project_pm is not None:
                return identity
        elif employee is not None:
            is_assignee = task.assigned_to == employee.emp_id
            is_project_team_member = db.query(TeamMember.team_member_id).join(
                Team, Team.team_id == TeamMember.team_id
            ).filter(
                Team.project_id == task.project_id,
                TeamMember.emp_id == employee.emp_id,
            ).first() is not None
            if is_assignee or is_project_team_member:
                return identity

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this task or a member of its project team.",
        )

    @staticmethod
    def _counterpart_account_ids(
        db: Session,
        task: Task,
        author: Optional[Employee],
        is_pm: bool,
        is_team_lead: bool,
    ) -> List[object]:
        """Resolve distinct notification recipients for the author's task counterpart."""
        recipients = []
        if author is not None and task.assigned_to == author.emp_id:
            recipients = db.query(Employee.account_id).join(
                Team, Team.lead_emp_id == Employee.emp_id
            ).filter(
                Team.project_id == task.project_id,
                Employee.account_id.is_not(None),
                Employee.emp_id != author.emp_id,
            ).distinct().all()
        elif is_pm or is_team_lead or author is None or (author is not None and task.assigned_to != author.emp_id):
            assignee = db.query(Employee.account_id).filter(
                Employee.emp_id == task.assigned_to,
                Employee.account_id.is_not(None),
            ).first()
            if assignee:
                recipients = [assignee]
        return list(dict.fromkeys(row[0] for row in recipients if row[0] is not None))

    @classmethod
    def create_comment(cls, db: Session, task_id: int, content: str, current_user: UserAccount) -> TaskCommentResponse:
        task = cls._task_or_404(db, task_id)
        author, author_name, author_role, is_pm, is_team_lead = cls._authorize_scope(db, task, current_user)
        comment = TaskComment(
            task_id=task.task_id,
            author_emp_id=author.emp_id if author else None,
            author_name=author_name,
            author_role=author_role,
            content=content,
        )
        db.add(comment)
        db.flush()

        for account_id in cls._counterpart_account_ids(db, task, author, is_pm, is_team_lead):
            if account_id == current_user.account_id:
                continue
            NotificationService.create_notification(
                db=db,
                user_id=account_id,
                type="TASK_COMMENT",
                title="New task comment",
                message=f"{author_name} commented on task #{task.task_id} '{task.title}'.",
                link=f"/tasks/{task.task_id}",
            )

        db.commit()
        db.refresh(comment)
        return TaskCommentResponse.model_validate(comment)

    @classmethod
    def list_comments(cls, db: Session, task_id: int, current_user: UserAccount) -> List[TaskCommentResponse]:
        task = cls._task_or_404(db, task_id)
        cls._authorize_scope(db, task, current_user)
        comments = db.query(TaskComment).filter(
            TaskComment.task_id == task.task_id
        ).order_by(TaskComment.created_at.asc(), TaskComment.comment_id.asc()).all()
        return [
            TaskCommentResponse(
                comment_id=comment.comment_id,
                task_id=comment.task_id,
                author_emp_id=comment.author_emp_id,
                author_name=comment.author_name or "Former user",
                author_role=comment.author_role or "UNKNOWN",
                content=comment.content,
                created_at=comment.created_at,
                edited_at=comment.edited_at,
            )
            for comment in comments
        ]
