from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee
from app.models.enums import CommonStatus, PriorityLevel, TaskStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.task import Task
from app.models.team import Team, TeamMember


class TaskRepository:
    """Data-access layer for Task CRUD and lookup queries."""

    @staticmethod
    def get_project_by_id(db: Session, project_id: int) -> Optional[Project]:
        return db.query(Project).filter(Project.project_id == project_id).first()

    @staticmethod
    def get_team_by_id(db: Session, team_id: int) -> Optional[Team]:
        return db.query(Team).filter(Team.team_id == team_id).first()

    @staticmethod
    def get_milestone_by_id(db: Session, milestone_id: int) -> Optional[ProjectMilestone]:
        return (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.id == milestone_id,
                ProjectMilestone.is_deleted.is_(False),
            )
            .first()
        )

    @staticmethod
    def get_employee_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        return db.query(Employee).filter(Employee.emp_id == emp_id).first()

    @staticmethod
    def get_employee_by_account_id(db: Session, account_id: UUID) -> Optional[Employee]:
        return db.query(Employee).filter(Employee.account_id == account_id).first()

    @staticmethod
    def is_active_team_member(db: Session, team_id: int, emp_id: int) -> bool:
        """Return True if the employee is an active member of the given team."""
        member = (
            db.query(TeamMember)
            .join(Employee, TeamMember.emp_id == Employee.emp_id)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.emp_id == emp_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .first()
        )
        return member is not None

    @staticmethod
    def create_task(db: Session, task: Task) -> Task:
        db.add(task)
        db.flush()
        db.refresh(task)
        return task

    @staticmethod
    def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
        return (
            db.query(Task)
            .options(
                joinedload(Task.project),
                joinedload(Task.milestone),
                joinedload(Task.assignee),
                joinedload(Task.creator),
            )
            .filter(Task.task_id == task_id)
            .first()
        )

    @staticmethod
    def list_my_tasks(
        db: Session,
        emp_id: int,
        status: Optional[TaskStatus] = None,
        priority: Optional[PriorityLevel] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Task], int]:
        query = db.query(Task).filter(Task.assigned_to == emp_id)

        if status is not None:
            query = query.filter(Task.status == status)
        if priority is not None:
            query = query.filter(Task.priority == priority)

        total = query.count()
        offset = (page - 1) * limit
        items = (
            query.order_by(Task.created_at.desc(), Task.task_id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    @staticmethod
    def list_project_tasks(
        db: Session,
        project_id: int,
        team_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Task], int]:
        query = db.query(Task).filter(Task.project_id == project_id)

        if team_id is not None:
            query = query.filter(Task.team_id == team_id)
        if milestone_id is not None:
            query = query.filter(Task.milestone_id == milestone_id)
        if status is not None:
            query = query.filter(Task.status == status)

        total = query.count()
        offset = (page - 1) * limit
        items = (
            query.order_by(Task.created_at.desc(), Task.task_id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
