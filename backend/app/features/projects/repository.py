from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.client import Client
from app.models.employee import Employee
from app.models.team import Team, TeamMember


class ProjectRepository:
    """Database repository for Projects, Assignments, Teams, and Memberships."""

    @staticmethod
    def create_project(db: Session, project: Project) -> Project:
        """Add and flush a new project."""
        db.add(project)
        db.flush()
        return project

    @staticmethod
    def get_project_by_id(db: Session, project_id: int) -> Optional[Project]:
        """Fetch project by primary key."""
        return db.query(Project).filter(Project.project_id == project_id).first()

    @staticmethod
    def get_project_by_code(db: Session, project_code: str) -> Optional[Project]:
        """Fetch project by unique project code (case-insensitive)."""
        return (
            db.query(Project)
            .filter(func.lower(Project.project_code) == func.lower(project_code.strip()))
            .first()
        )

    @staticmethod
    def list_projects(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        pm_id: Optional[int] = None,
        emp_id: Optional[int] = None,
    ) -> Tuple[List[Project], int]:
        """
        List projects:
        - If pm_id provided: projects managed by that PM.
        - If emp_id provided: projects where employee has an active assignment.
        - Otherwise: all projects.
        """
        query = db.query(Project)

        if pm_id is not None:
            query = query.filter(Project.pm_id == pm_id)
        elif emp_id is not None:
            query = query.join(
                ProjectAssignment, ProjectAssignment.project_id == Project.project_id
            ).filter(
                ProjectAssignment.emp_id == emp_id,
                ProjectAssignment.released_on.is_(None),
            )

        total_count = query.count()
        items = query.order_by(Project.project_id.desc()).offset(skip).limit(limit).all()
        return items, total_count

    @staticmethod
    def get_pm_by_account_id(db: Session, account_id: UUID) -> Optional[ProjectManager]:
        """Fetch ProjectManager record linked to a UserAccount UUID."""
        return (
            db.query(ProjectManager)
            .filter(ProjectManager.account_id == account_id)
            .first()
        )

    @staticmethod
    def get_pm_by_id(db: Session, pm_id: int) -> Optional[ProjectManager]:
        """Fetch ProjectManager by PM ID."""
        return db.query(ProjectManager).filter(ProjectManager.pm_id == pm_id).first()

    @staticmethod
    def get_client_by_id(db: Session, client_id: int) -> Optional[Client]:
        """Fetch Client by client ID."""
        return db.query(Client).filter(Client.client_id == client_id).first()

    @staticmethod
    def get_employee_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        """Fetch Employee by emp_id."""
        return db.query(Employee).filter(Employee.emp_id == emp_id).first()

    @staticmethod
    def create_assignment(db: Session, assignment: ProjectAssignment) -> ProjectAssignment:
        """Add and flush a project assignment."""
        db.add(assignment)
        db.flush()
        return assignment

    @staticmethod
    def get_active_assignment(
        db: Session, project_id: int, emp_id: int
    ) -> Optional[ProjectAssignment]:
        """Check if employee is actively assigned to project (released_on IS NULL)."""
        return (
            db.query(ProjectAssignment)
            .filter(
                ProjectAssignment.project_id == project_id,
                ProjectAssignment.emp_id == emp_id,
                ProjectAssignment.released_on.is_(None),
            )
            .first()
        )

    @staticmethod
    def list_project_assignments(db: Session, project_id: int) -> List[ProjectAssignment]:
        """List all assignments for a project."""
        return (
            db.query(ProjectAssignment)
            .filter(ProjectAssignment.project_id == project_id)
            .order_by(ProjectAssignment.assignment_id.asc())
            .all()
        )

    @staticmethod
    def create_team(db: Session, team: Team) -> Team:
        """Add and flush a team."""
        db.add(team)
        db.flush()
        return team

    @staticmethod
    def get_team_by_id(db: Session, team_id: int) -> Optional[Team]:
        """Fetch team by ID."""
        return db.query(Team).filter(Team.team_id == team_id).first()

    @staticmethod
    def list_project_teams(db: Session, project_id: int) -> List[Team]:
        """List all teams associated with a project."""
        return (
            db.query(Team)
            .filter(Team.project_id == project_id)
            .order_by(Team.team_id.asc())
            .all()
        )

    @staticmethod
    def add_team_member(db: Session, member: TeamMember) -> TeamMember:
        """Add and flush a team member."""
        db.add(member)
        db.flush()
        return member

    @staticmethod
    def get_team_member(db: Session, team_id: int, emp_id: int) -> Optional[TeamMember]:
        """Check if an employee is already in a team."""
        return (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.emp_id == emp_id)
            .first()
        )

    @staticmethod
    def list_team_members(db: Session, team_id: int) -> List[TeamMember]:
        """List members of a specific team."""
        return (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id)
            .order_by(TeamMember.team_member_id.asc())
            .all()
        )
