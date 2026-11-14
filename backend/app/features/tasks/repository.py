from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.enums import CommonStatus, TaskStatus
from app.models.project import ProjectAssignment
from app.models.task import Task
from app.models.team import Team, TeamMember


class TaskRepository:
    """Repository handling database interactions for Task management, assignment, and progress tracking (US-09, US-10, US-14)."""

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
    def is_employee_member_of_team(db: Session, emp_id: int, team_id: int) -> bool:
        """Check if an employee is an active member or lead of a team."""
        # 1. Check if employee is team lead
        is_lead = (
            db.query(Team)
            .filter(Team.team_id == team_id, Team.lead_emp_id == emp_id)
            .first()
            is not None
        )
        if is_lead:
            return True

        # 2. Check if active team member in team_member table
        return (
            db.query(TeamMember)
            .join(Employee, Employee.emp_id == TeamMember.emp_id)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.emp_id == emp_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .first()
            is not None
        )

    @staticmethod
    def is_employee_on_project_roster(db: Session, emp_id: int, project_id: int) -> bool:
        """Check if an employee is on a project via a team or direct assignment."""
        # Check team membership on project teams
        project_team_member = (
            db.query(TeamMember)
            .join(Team, Team.team_id == TeamMember.team_id)
            .join(Employee, Employee.emp_id == TeamMember.emp_id)
            .filter(
                Team.project_id == project_id,
                TeamMember.emp_id == emp_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .first()
            is not None
        )
        if project_team_member:
            return True

        # Check project team lead
        project_team_lead = (
            db.query(Team)
            .filter(Team.project_id == project_id, Team.lead_emp_id == emp_id)
            .first()
            is not None
        )
        if project_team_lead:
            return True

        # Check project assignment roster
        return (
            db.query(ProjectAssignment)
            .filter(
                ProjectAssignment.project_id == project_id,
                ProjectAssignment.emp_id == emp_id,
                ProjectAssignment.released_on.is_(None),
            )
            .first()
            is not None
        )

    @staticmethod
    def is_employee_eligible_assignee(db: Session, emp_id: int, task: Task) -> bool:
        """Verify if an employee is eligible to be assigned to this task."""
        if getattr(task, "team_id", None) is not None:
            return TaskRepository.is_employee_member_of_team(db, emp_id=emp_id, team_id=task.team_id)
        return TaskRepository.is_employee_on_project_roster(db, emp_id=emp_id, project_id=task.project_id)

    @staticmethod
    def assign_task(db: Session, task: Task, assignee_id: int) -> Task:
        """Assign task to an employee and persist."""
        task.assigned_to = assignee_id
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def reassign_task(db: Session, task: Task, new_assignee_id: int) -> Task:
        """Reassign task to a new employee and persist."""
        task.assigned_to = new_assignee_id
        db.commit()
        db.refresh(task)
        return task

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
