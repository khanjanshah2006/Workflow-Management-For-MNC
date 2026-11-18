"""Shared actor-resolution and scope helpers for Wave 3 features.

Scope rules (see the Wave 3 shared conventions):
- Team Lead of an employee: the employee is a member of an ACTIVE team whose
  lead_emp_id is the caller.
- PM of a project: project.pm_id == caller's pm_id.
- Staffing PMs of an employee: PMs of PLANNED/ACTIVE projects where the
  employee has an unreleased ProjectAssignment.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.enums import ProjectStatus, TeamStatus
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.system_parameter import SystemParameter
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount

_STAFFING_PROJECT_STATUSES = (ProjectStatus.PLANNED, ProjectStatus.ACTIVE)


def resolve_employee(db: Session, user: UserAccount) -> Employee | None:
    return db.scalar(select(Employee).where(Employee.account_id == user.account_id))


def resolve_pm(db: Session, user: UserAccount) -> ProjectManager | None:
    return db.scalar(select(ProjectManager).where(ProjectManager.account_id == user.account_id))


def led_team_ids(db: Session, lead_emp_id: int) -> set[int]:
    """IDs of ACTIVE teams led by this employee."""
    stmt = select(Team.team_id).where(
        Team.lead_emp_id == lead_emp_id,
        Team.status == TeamStatus.ACTIVE,
    )
    return set(db.scalars(stmt))


def employee_team_ids(db: Session, emp_id: int) -> set[int]:
    """IDs of ACTIVE teams this employee is a member of."""
    stmt = (
        select(TeamMember.team_id)
        .join(Team, Team.team_id == TeamMember.team_id)
        .where(TeamMember.emp_id == emp_id, Team.status == TeamStatus.ACTIVE)
    )
    return set(db.scalars(stmt))


def is_team_lead_of(db: Session, lead_emp_id: int, target_emp_id: int) -> bool:
    """True if target is a member of an ACTIVE team led by lead_emp_id."""
    stmt = (
        select(TeamMember.team_member_id)
        .join(Team, Team.team_id == TeamMember.team_id)
        .where(
            TeamMember.emp_id == target_emp_id,
            Team.lead_emp_id == lead_emp_id,
            Team.status == TeamStatus.ACTIVE,
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def team_lead_account_ids_for(db: Session, emp_id: int) -> list[UUID]:
    """Account IDs of the leads of the employee's ACTIVE teams, excluding the employee."""
    stmt = (
        select(Employee.account_id)
        .join(Team, Team.lead_emp_id == Employee.emp_id)
        .join(TeamMember, TeamMember.team_id == Team.team_id)
        .where(
            TeamMember.emp_id == emp_id,
            Team.status == TeamStatus.ACTIVE,
            Employee.emp_id != emp_id,
            Employee.account_id.is_not(None),
        )
        .distinct()
    )
    return list(db.scalars(stmt))


def pm_manages_project(db: Session, pm_id: int, project_id: int) -> bool:
    stmt = select(Project.project_id).where(
        Project.project_id == project_id,
        Project.pm_id == pm_id,
    )
    return db.scalar(stmt) is not None


def staffing_projects_for(db: Session, emp_id: int) -> list[Project]:
    """PLANNED/ACTIVE projects the employee is currently (unreleased) assigned to."""
    stmt = (
        select(Project)
        .join(ProjectAssignment, ProjectAssignment.project_id == Project.project_id)
        .where(
            ProjectAssignment.emp_id == emp_id,
            ProjectAssignment.released_on.is_(None),
            Project.status.in_(_STAFFING_PROJECT_STATUSES),
        )
        .distinct()
        .order_by(Project.project_id)
    )
    return list(db.scalars(stmt))


def staffing_pm_account_ids_for(db: Session, emp_id: int) -> list[UUID]:
    """Account IDs of PMs of the employee's staffing projects."""
    stmt = (
        select(ProjectManager.account_id)
        .join(Project, Project.pm_id == ProjectManager.pm_id)
        .join(ProjectAssignment, ProjectAssignment.project_id == Project.project_id)
        .where(
            ProjectAssignment.emp_id == emp_id,
            ProjectAssignment.released_on.is_(None),
            Project.status.in_(_STAFFING_PROJECT_STATUSES),
            ProjectManager.account_id.is_not(None),
        )
        .distinct()
    )
    return list(db.scalars(stmt))


def get_int_param(db: Session, key: str, default: int) -> int:
    """Read an integer SystemParameter; fall back to default if missing or not an int."""
    value = db.scalar(select(SystemParameter.value).where(SystemParameter.key == key))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
