from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.task import Task, TaskSubmission
from app.models.employee import Employee
from app.models.team import Team, TeamMember
from app.models.enums import TaskStatus, PriorityLevel


class TaskRepository:
    """Database operations for Task lifecycle and review triage queue (US-13)."""

    @staticmethod
    def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
        """Fetch task by primary key."""
        return db.query(Task).filter(Task.task_id == task_id).first()

    @staticmethod
    def get_review_queue(
        db: Session,
        team_id: Optional[int] = None,
        priority: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> List[Tuple[Task, Optional[Employee], Optional[TaskSubmission]]]:
        """
        Query tasks in IN_REVIEW status scoped to the given team_id,
        ordered with pagination. Returns tuples of (Task, Employee, latest TaskSubmission).
        """
        query = (
            db.query(Task, Employee)
            .outerjoin(Employee, Task.assigned_to == Employee.emp_id)
            .filter(Task.status == TaskStatus.IN_REVIEW)
        )

        if team_id is not None:
            query = query.filter(Task.team_id == team_id)

        if priority:
            priority_clean = str(priority).strip().upper()
            try:
                priority_enum = PriorityLevel(priority_clean)
                query = query.filter(Task.priority == priority_enum)
            except (ValueError, KeyError):
                query = query.filter(Task.priority == priority_clean)

        offset = max(0, (page - 1) * limit)
        results = query.order_by(desc(Task.created_at)).offset(offset).limit(limit).all()

        # For each task, fetch its most recent submission
        items: List[Tuple[Task, Optional[Employee], Optional[TaskSubmission]]] = []
        for task, employee in results:
            latest_submission = (
                db.query(TaskSubmission)
                .filter(TaskSubmission.task_id == task.task_id)
                .order_by(desc(TaskSubmission.created_at))
                .first()
            )
            items.append((task, employee, latest_submission))

        return items

    @staticmethod
    def create_submission(
        db: Session,
        task_id: int,
        submitted_by: Optional[int],
        remarks: str,
        file_url: Optional[str] = None,
    ) -> TaskSubmission:
        """Create and flush a new task_submission record."""
        submission = TaskSubmission(
            task_id=task_id,
            submitted_by=submitted_by,
            remarks=remarks,
            file_url=file_url,
        )
        db.add(submission)
        db.flush()
        db.refresh(submission)
        return submission

    @staticmethod
    def update_task_status(db: Session, task: Task, new_status: TaskStatus) -> Task:
        """Update task status and flush changes."""
        task.status = new_status
        db.flush()
        db.refresh(task)
        return task

    @staticmethod
    def get_employee_by_account_id(db: Session, account_id: UUID) -> Optional[Employee]:
        """Resolve employee entity from user_account UUID."""
        return db.query(Employee).filter(Employee.account_id == account_id).first()

    @staticmethod
    def get_employee_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        """Fetch employee by integer ID."""
        return db.query(Employee).filter(Employee.emp_id == emp_id).first()

    @staticmethod
    def get_team_by_id(db: Session, team_id: int) -> Optional[Team]:
        """Fetch team by primary key."""
        return db.query(Team).filter(Team.team_id == team_id).first()

    @staticmethod
    def get_team_lead_employee(db: Session, team_id: int) -> Optional[Employee]:
        """Locate the designated Team Lead for a team."""
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if team and team.lead_emp_id:
            return db.query(Employee).filter(Employee.emp_id == team.lead_emp_id).first()
        return None

    @staticmethod
    def get_team_for_employee(db: Session, emp_id: int) -> Optional[Team]:
        """
        Locate team associated with employee, either as team lead or member.
        """
        lead_team = db.query(Team).filter(Team.lead_emp_id == emp_id).first()
        if lead_team:
            return lead_team
        member_link = db.query(TeamMember).filter(TeamMember.emp_id == emp_id).first()
        if member_link:
            return db.query(Team).filter(Team.team_id == member_link.team_id).first()
        return None
