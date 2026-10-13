from datetime import date
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectAssignment
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount
from app.models.enums import ProjectStatus, TeamStatus, UserType, AuditAction
from app.core.audit import write_audit_log
from app.features.projects.repository import ProjectRepository
from app.features.projects.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectAssignmentCreate,
    ProjectAssignmentResponse,
    TeamCreate,
    TeamResponse,
    TeamMemberAdd,
    TeamMemberResponse,
)


# ==========================================
# Domain Exceptions
# ==========================================

class ProjectServiceError(Exception):
    """Base exception for Project service."""
    pass


class ProjectNotFoundError(ProjectServiceError):
    def __init__(self, project_id: int):
        self.project_id = project_id
        super().__init__(f"Project with ID {project_id} not found")


class ProjectCodeAlreadyExistsError(ProjectServiceError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Project code '{code}' already exists")


class ClientNotFoundError(ProjectServiceError):
    def __init__(self, client_id: int):
        self.client_id = client_id
        super().__init__(f"Client with ID {client_id} not found")


class ProjectManagerNotFoundError(ProjectServiceError):
    def __init__(self, pm_id_or_account: str):
        super().__init__(f"Project Manager '{pm_id_or_account}' not found")


class EmployeeNotFoundError(ProjectServiceError):
    def __init__(self, emp_id: int):
        self.emp_id = emp_id
        super().__init__(f"Employee with ID {emp_id} not found")


class EmployeeNotAssignedToProjectError(ProjectServiceError):
    def __init__(self, emp_id: int, project_id: int):
        self.emp_id = emp_id
        self.project_id = project_id
        super().__init__(f"Employee {emp_id} is not actively assigned to project {project_id}. Assign to project first.")


class EmployeeAlreadyAssignedError(ProjectServiceError):
    def __init__(self, emp_id: int, project_id: int):
        super().__init__(f"Employee {emp_id} already holds an active assignment for project {project_id}")


class TeamNotFoundError(ProjectServiceError):
    def __init__(self, team_id: int):
        self.team_id = team_id
        super().__init__(f"Team with ID {team_id} not found")


class TeamMemberAlreadyExistsError(ProjectServiceError):
    def __init__(self, team_id: int, emp_id: int):
        super().__init__(f"Employee {emp_id} is already a member of team {team_id}")


class InvalidDateRangeError(ProjectServiceError):
    def __init__(self, message: str = "Project end_date must be on or after start_date"):
        super().__init__(message)


class UnauthorizedProjectAccessError(ProjectServiceError):
    def __init__(self, message: str = "You are not authorized to manage this project"):
        super().__init__(message)


# ==========================================
# Service Implementation
# ==========================================

class ProjectService:
    """Business logic for Project Lifecycle, Staffing, and Team Structuring (US-06, US-07)."""

    @staticmethod
    def _is_admin(user: UserAccount) -> bool:
        role = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        return role.upper() in ["ADMIN"]

    @staticmethod
    def _resolve_pm_id(db: Session, payload: ProjectCreate, current_user: UserAccount) -> int:
        """Resolve PM ID from payload or logged-in UserAccount."""
        if payload.pm_id:
            pm = ProjectRepository.get_pm_by_id(db, payload.pm_id)
            if not pm:
                raise ProjectManagerNotFoundError(str(payload.pm_id))
            return pm.pm_id

        # Otherwise resolve from current_user
        pm = ProjectRepository.get_pm_by_account_id(db, current_user.account_id)
        if not pm:
            raise ProjectManagerNotFoundError(f"Account {current_user.account_id}")
        return pm.pm_id

    @staticmethod
    def _verify_pm_ownership(db: Session, project: Project, current_user: UserAccount) -> None:
        """Ensure current user is the project's assigned PM or an Admin."""
        if ProjectService._is_admin(current_user):
            return

        pm = ProjectRepository.get_pm_by_account_id(db, current_user.account_id)
        if not pm or pm.pm_id != project.pm_id:
            raise UnauthorizedProjectAccessError("Only the assigned Project Manager can modify this project")

    # ------------------------------------------
    # Project Operations (US-06)
    # ------------------------------------------

    @staticmethod
    def create_project(
        db: Session,
        payload: ProjectCreate,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ProjectResponse:
        """Create a new project with client and PM validation."""
        # 1. Date validation
        if payload.end_date and payload.end_date < payload.start_date:
            raise InvalidDateRangeError()

        # 2. Client validation
        client = ProjectRepository.get_client_by_id(db, payload.client_id)
        if not client:
            raise ClientNotFoundError(payload.client_id)

        # 3. PM resolution
        pm_id = ProjectService._resolve_pm_id(db, payload, current_user)

        # 4. Unique project_code check
        if ProjectRepository.get_project_by_code(db, payload.project_code):
            raise ProjectCodeAlreadyExistsError(payload.project_code)

        # 5. Create project entity
        project = Project(
            client_id=payload.client_id,
            pm_id=pm_id,
            project_code=payload.project_code.strip().upper(),
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            start_date=payload.start_date,
            end_date=payload.end_date,
            priority=payload.priority,
            status=ProjectStatus.PLANNED,
        )
        ProjectRepository.create_project(db, project)
        db.commit()
        db.refresh(project)

        # 6. Audit log
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="PROJECT",
            entity_ref_id=str(project.project_id),
            account_id=current_user.account_id,
            new_value={
                "project_code": project.project_code,
                "name": project.name,
                "pm_id": project.pm_id,
                "client_id": project.client_id,
            },
            ip_address=ip_address,
        )

        return ProjectResponse.model_validate(project)

    @staticmethod
    def list_projects(
        db: Session,
        current_user: UserAccount,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ProjectResponse], int]:
        """List projects filtered by user scope (PM sees theirs; Employee sees assigned)."""
        role = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
        role = role.upper()

        pm_id = None
        emp_id = None

        if role == "PM":
            pm = ProjectRepository.get_pm_by_account_id(db, current_user.account_id)
            if pm:
                pm_id = pm.pm_id
        elif role == "EMPLOYEE":
            # Find employee by account_id
            emp = db.query(ProjectRepository.get_employee_by_id(db, 0).__class__).filter_by(account_id=current_user.account_id).first()
            if emp:
                emp_id = emp.emp_id

        projects, total = ProjectRepository.list_projects(
            db=db, skip=skip, limit=limit, pm_id=pm_id, emp_id=emp_id
        )
        return [ProjectResponse.model_validate(p) for p in projects], total

    @staticmethod
    def get_project(db: Session, project_id: int) -> ProjectResponse:
        """Fetch project by ID."""
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        return ProjectResponse.model_validate(project)

    # ------------------------------------------
    # Staffing / Assignment Operations (US-07)
    # ------------------------------------------

    @staticmethod
    def assign_employee(
        db: Session,
        project_id: int,
        payload: ProjectAssignmentCreate,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ProjectAssignmentResponse:
        """Allocate an employee to a project (PROJECT_ASSIGNMENT)."""
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)

        ProjectService._verify_pm_ownership(db, project, current_user)

        employee = ProjectRepository.get_employee_by_id(db, payload.emp_id)
        if not employee:
            raise EmployeeNotFoundError(payload.emp_id)

        # Check existing active assignment
        if ProjectRepository.get_active_assignment(db, project_id, payload.emp_id):
            raise EmployeeAlreadyAssignedError(payload.emp_id, project_id)

        assignment = ProjectAssignment(
            project_id=project_id,
            emp_id=payload.emp_id,
            role_in_project=payload.role_in_project.strip(),
            assigned_on=date.today(),
        )
        ProjectRepository.create_assignment(db, assignment)
        db.commit()
        db.refresh(assignment)

        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="PROJECT_ASSIGNMENT",
            entity_ref_id=str(assignment.assignment_id),
            account_id=current_user.account_id,
            new_value={
                "project_id": project_id,
                "emp_id": payload.emp_id,
                "role_in_project": assignment.role_in_project,
            },
            ip_address=ip_address,
        )

        return ProjectAssignmentResponse.model_validate(assignment)

    @staticmethod
    def list_assignments(db: Session, project_id: int) -> List[ProjectAssignmentResponse]:
        """List all assignments on a project."""
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        assignments = ProjectRepository.list_project_assignments(db, project_id)
        return [ProjectAssignmentResponse.model_validate(a) for a in assignments]

    # ------------------------------------------
    # Team & Membership Operations (US-07)
    # ------------------------------------------

    @staticmethod
    def create_team(
        db: Session,
        project_id: int,
        payload: TeamCreate,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> TeamResponse:
        """Create a team within a project."""
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)

        ProjectService._verify_pm_ownership(db, project, current_user)

        if payload.lead_emp_id:
            lead = ProjectRepository.get_employee_by_id(db, payload.lead_emp_id)
            if not lead:
                raise EmployeeNotFoundError(payload.lead_emp_id)
            # Lead must be assigned to project first
            if not ProjectRepository.get_active_assignment(db, project_id, payload.lead_emp_id):
                raise EmployeeNotAssignedToProjectError(payload.lead_emp_id, project_id)

        team = Team(
            project_id=project_id,
            lead_emp_id=payload.lead_emp_id,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            status=TeamStatus.ACTIVE,
        )
        ProjectRepository.create_team(db, team)
        db.flush()

        # If lead specified, add as team member automatically
        if payload.lead_emp_id:
            lead_member = TeamMember(team_id=team.team_id, emp_id=payload.lead_emp_id)
            ProjectRepository.add_team_member(db, lead_member)

        db.commit()
        db.refresh(team)

        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="TEAM",
            entity_ref_id=str(team.team_id),
            account_id=current_user.account_id,
            new_value={"name": team.name, "project_id": project_id, "lead_emp_id": payload.lead_emp_id},
            ip_address=ip_address,
        )

        return TeamResponse.model_validate(team)

    @staticmethod
    def list_teams(db: Session, project_id: int) -> List[TeamResponse]:
        """List all teams inside a project."""
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        teams = ProjectRepository.list_project_teams(db, project_id)
        return [TeamResponse.model_validate(t) for t in teams]

    @staticmethod
    def add_team_member(
        db: Session,
        project_id: int,
        team_id: int,
        payload: TeamMemberAdd,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> TeamMemberResponse:
        """
        Add employee to team.
        ENFORCES STRICT BUSINESS RULE: Employee must hold active PROJECT_ASSIGNMENT first!
        """
        project = ProjectRepository.get_project_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)

        ProjectService._verify_pm_ownership(db, project, current_user)

        team = ProjectRepository.get_team_by_id(db, team_id)
        if not team or team.project_id != project_id:
            raise TeamNotFoundError(team_id)

        # 1. Enforce active project assignment
        if not ProjectRepository.get_active_assignment(db, project_id, payload.emp_id):
            raise EmployeeNotAssignedToProjectError(payload.emp_id, project_id)

        # 2. Check if already member
        if ProjectRepository.get_team_member(db, team_id, payload.emp_id):
            raise TeamMemberAlreadyExistsError(team_id, payload.emp_id)

        member = TeamMember(team_id=team_id, emp_id=payload.emp_id)
        ProjectRepository.add_team_member(db, member)
        db.commit()
        db.refresh(member)

        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="TEAM_MEMBER",
            entity_ref_id=str(member.team_member_id),
            account_id=current_user.account_id,
            new_value={"team_id": team_id, "emp_id": payload.emp_id},
            ip_address=ip_address,
        )

        return TeamMemberResponse.model_validate(member)

    @staticmethod
    def list_team_members(db: Session, project_id: int, team_id: int) -> List[TeamMemberResponse]:
        """List all members of a team."""
        team = ProjectRepository.get_team_by_id(db, team_id)
        if not team or team.project_id != project_id:
            raise TeamNotFoundError(team_id)
        members = ProjectRepository.list_team_members(db, team_id)
        return [TeamMemberResponse.model_validate(m) for m in members]
