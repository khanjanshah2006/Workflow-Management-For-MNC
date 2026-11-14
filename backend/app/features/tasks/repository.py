from typing import List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee
from app.models.enums import CommonStatus, PriorityLevel, TaskStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.task import Task, TaskSubmission
from app.models.team import Team, TeamMember


class TaskRepository:
    """Unified data-access layer for Task CRUD, progress tracking, and review queue."""

    # ── US-09 / US-32 Operations ──────────────────────────────────────────

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

    # ── US-13 Operations (Review Queue & Triage) ─────────────────────────

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

        items: List[Tuple[Task, Optional[Employee], Optional[TaskSubmission]]] = []
        for task, employee in results:
            latest_submission = (
                db.query(TaskSubmission)
                .filter(TaskSubmission.task_id == task.task_id)
                .order_by(desc(TaskSubmission.submitted_at))
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
        task.status = new_status
        db.flush()
        db.refresh(task)
        return task

    # ── US-10 Operations (Task Progress & Blockers) ───────────────────────

    @staticmethod
    def get_team_for_employee(db: Session, emp_id: int) -> Optional[Team]:
        lead_team = db.query(Team).filter(Team.lead_emp_id == emp_id).first()
        if lead_team:
            return lead_team
        member_link = db.query(TeamMember).filter(TeamMember.emp_id == emp_id).first()
        if member_link:
            return db.query(Team).filter(Team.team_id == member_link.team_id).first()
        return None

    @staticmethod
    def get_team_for_task(db: Session, task: Task) -> Optional[Team]:
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
    def get_team_lead_employee(db: Session, team_or_id: Union[Optional[Team], int]) -> Optional[Employee]:
        if isinstance(team_or_id, int):
            team = db.query(Team).filter(Team.team_id == team_or_id).first()
        else:
            team = team_or_id

        if not team or not team.lead_emp_id:
            return None
        return db.query(Employee).filter(Employee.emp_id == team.lead_emp_id).first()

    @staticmethod
    def is_team_lead_for_task(db: Session, emp_id: int, task: Task) -> bool:
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
        task.status = status
        task.progress_pct = progress_pct
        task.blocker_reason = blocker_reason
        db.flush()
        db.refresh(task)
        return task
