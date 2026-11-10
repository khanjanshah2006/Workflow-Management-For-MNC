from typing import Optional
from sqlalchemy.orm import Session

from app.models.enums import CommonStatus
from app.models.employee import Employee
from app.models.project import ProjectAssignment
from app.models.task import Task
from app.models.team import Team, TeamMember


class TaskRepository:
    """Database interactions for task management (US-09, US-14)."""

    @staticmethod
    def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
        """Fetch a task by primary key."""
        return db.query(Task).filter(Task.task_id == task_id).first()

    @staticmethod
    def get_employee_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        """Fetch an employee by primary key."""
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
        if task.team_id is not None:
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
