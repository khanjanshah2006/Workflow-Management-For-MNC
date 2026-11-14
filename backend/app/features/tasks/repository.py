from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.team import Team, TeamMember


class TaskRepository:
    """Repository handling database interactions for Task management and progress tracking (US-10)."""

    @staticmethod
    def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
        """Fetch a single task by its primary key ID."""
        return db.query(Task).filter(Task.task_id == task_id).first()

    @staticmethod
    def get_employee_by_account_id(db: Session, account_id: UUID) -> Optional[Employee]:
        """Look up an employee profile by linked user account ID."""
        return db.query(Employee).filter(Employee.account_id == account_id).first()

    @staticmethod
    def get_employee_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        """Fetch employee by primary key emp_id."""
        return db.query(Employee).filter(Employee.emp_id == emp_id).first()

    @staticmethod
    def get_team_for_task(db: Session, task: Task) -> Optional[Team]:
        """
        Determine the Team associated with a given task.
        Checks:
        1. Direct task.team_id if present
        2. Assignee's team membership via TeamMember
        3. Project's designated team
        """
        if getattr(task, "team_id", None):
            team = db.query(Team).filter(Team.team_id == task.team_id).first()
            if team:
                return team

        if task.assigned_to:
            membership = db.query(TeamMember).filter(TeamMember.emp_id == task.assigned_to).first()
            if membership:
                team = db.query(Team).filter(Team.team_id == membership.team_id).first()
                if team:
                    return team

        if task.project_id:
            team = db.query(Team).filter(Team.project_id == task.project_id).first()
            if team:
                return team

        return None

    @staticmethod
    def get_team_lead_employee(db: Session, team: Optional[Team]) -> Optional[Employee]:
        """Retrieve the Employee record for the lead of a team."""
        if not team or not team.lead_emp_id:
            return None
        return db.query(Employee).filter(Employee.emp_id == team.lead_emp_id).first()

    @staticmethod
    def is_team_lead_for_task(db: Session, emp_id: int, task: Task) -> bool:
        """Check whether an employee is the Team Lead of the team owning this task."""
        team = TaskRepository.get_team_for_task(db, task)
        if not team:
            return False
        return team.lead_emp_id == emp_id

    @staticmethod
    def update_task_progress(
        db: Session,
        task: Task,
        status: TaskStatus,
        progress_pct: int,
        blocker_reason: Optional[str] = None,
    ) -> Task:
        """
        Persist updated task status, progress percentage, and blocker details.
        Commits are managed at the service level.
        """
        task.status = status
        task.progress_pct = progress_pct
        task.blocker_reason = blocker_reason

        db.flush()
        db.refresh(task)
        return task
