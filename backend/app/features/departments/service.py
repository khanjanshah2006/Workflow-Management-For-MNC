import json
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team
from app.models.user_account import UserAccount
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, UserType
from app.features.departments import repository
from app.features.departments.schemas import DepartmentCreate, DepartmentUpdate


class DepartmentServiceError(Exception):
    """Base exception for department service errors."""
    pass


class DepartmentNotFoundError(DepartmentServiceError):
    """Raised when a requested department is not found."""

    def __init__(self, dept_id: int):
        self.dept_id = dept_id
        super().__init__(f"Department with ID {dept_id} not found")


class DepartmentAlreadyExistsError(DepartmentServiceError):
    """Raised when a department with the given name already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Department with name '{name}' already exists")


class TeamNotFoundError(DepartmentServiceError):
    """Raised when a requested team is not found."""

    def __init__(self, team_id: int):
        self.team_id = team_id
        super().__init__(f"Team with ID {team_id} not found")


class TeamAccessForbiddenError(DepartmentServiceError):
    """Raised when caller lacks authorization to access the given team."""

    def __init__(self, team_id: int):
        self.team_id = team_id
        super().__init__(f"Access forbidden: you are not authorized to view team {team_id}")



def _record_audit_log(
    db: Session,
    action: AuditAction,
    dept_id: int,
    account_id: UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Helper to record an audit log entry within the active transaction."""
    audit_entry = AuditLog(
        account_id=account_id,
        action=action,
        entity_name="DEPARTMENT",
        entity_ref_id=str(dept_id),
        old_value=json.dumps(old_value) if old_value is not None else None,
        new_value=json.dumps(new_value) if new_value is not None else None,
        ip_address=ip_address,
    )
    db.add(audit_entry)
    return audit_entry


def get_department(db: Session, dept_id: int) -> Department:
    dept = repository.get_by_id(db, dept_id)
    if dept is None:
        raise DepartmentNotFoundError(dept_id)
    return dept


def list_departments(
    db: Session,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Department], int]:
    return repository.get_all(db, skip=skip, limit=limit)


def create_department(
    db: Session,
    department_in: DepartmentCreate,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> Department:
    existing = repository.get_by_name(db, department_in.name)
    if existing is not None:
        raise DepartmentAlreadyExistsError(department_in.name)

    try:
        department = repository.create(db, department_in)

        new_data = {
            "dept_id": department.dept_id,
            "name": department.name,
            "description": department.description,
        }
        _record_audit_log(
            db=db,
            action=AuditAction.CREATE,
            dept_id=department.dept_id,
            account_id=actor_account_id,
            new_value=new_data,
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(department)
        return department
    except Exception:
        db.rollback()
        raise


def update_department(
    db: Session,
    dept_id: int,
    department_in: DepartmentUpdate,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> Department:
    department = repository.get_by_id(db, dept_id)
    if department is None:
        raise DepartmentNotFoundError(dept_id)

    if department_in.name and department_in.name.lower() != department.name.lower():
        existing = repository.get_by_name(db, department_in.name)
        if existing is not None and existing.dept_id != dept_id:
            raise DepartmentAlreadyExistsError(department_in.name)

    try:
        old_data = {
            "name": department.name,
            "description": department.description,
        }

        department = repository.update(db, department, department_in)

        new_data = {
            "name": department.name,
            "description": department.description,
        }
        _record_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            dept_id=department.dept_id,
            account_id=actor_account_id,
            old_value=old_data,
            new_value=new_data,
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(department)
        return department
    except Exception:
        db.rollback()
        raise


def delete_department(
    db: Session,
    dept_id: int,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    department = repository.get_by_id(db, dept_id)
    if department is None:
        raise DepartmentNotFoundError(dept_id)

    old_data = {
        "dept_id": department.dept_id,
        "name": department.name,
        "description": department.description,
    }

    _record_audit_log(
        db=db,
        action=AuditAction.DELETE,
        dept_id=dept_id,
        account_id=actor_account_id,
        old_value=old_data,
        ip_address=ip_address,
    )

    repository.delete(db, department)
    db.commit()


# ==========================================
# Team Member & Task Services (US-37)
# ==========================================


def _resolve_employee_for_account(db: Session, account_id: UUID) -> Employee | None:
    """Find the linked employee record for a given user account."""
    stmt = select(Employee).where(Employee.account_id == account_id)
    return db.scalars(stmt).first()


def _assert_team_access(
    db: Session,
    team: Team,
    current_user: UserAccount,
) -> None:
    """
    Enforce US-37 RBAC scope:
    - HR and ADMIN (SysAdmin) can query any team's roster.
    - PM can query any team roster (project oversight).
    - Team Lead (EMPLOYEE where team.lead_emp_id == employee.emp_id) can query their own assigned team.
    - Other employees or clients attempting to query teams they do not lead receive 403 Forbidden.
    """
    user_type_val = (
        current_user.user_type.value
        if hasattr(current_user.user_type, "value")
        else str(current_user.user_type)
    ).upper()

    # HR, Admin, PM have unrestricted read access to team rosters
    if user_type_val in ("HR", "HR_MANAGER", "ADMIN", "PM", "PROJECT_MANAGER"):
        return

    # Employee must be the designated Team Lead for this specific team
    if user_type_val == "EMPLOYEE":
        emp = _resolve_employee_for_account(db, current_user.account_id)
        if emp is not None and team.lead_emp_id == emp.emp_id:
            return

    # All other roles or non-lead employees are forbidden
    raise TeamAccessForbiddenError(team.team_id)


def get_team_members(
    db: Session,
    team_id: int,
    current_user: UserAccount,
) -> list[Employee]:
    """
    Retrieve active employees assigned to team_id.
    - 404 if team does not exist.
    - 403 if user is not authorized.
    - Returns [] cleanly if team has no active members.
    """
    team = repository.get_team_by_id(db, team_id)
    if team is None:
        raise TeamNotFoundError(team_id)

    _assert_team_access(db, team, current_user)
    return repository.get_active_members_for_team(db, team_id)


def get_team_tasks(
    db: Session,
    team_id: int,
    current_user: UserAccount,
) -> list[Any]:
    """
    Stub endpoint returning [] until S3 tasks land.
    - 404 if team does not exist.
    - 403 if user is not authorized.
    """
    team = repository.get_team_by_id(db, team_id)
    if team is None:
        raise TeamNotFoundError(team_id)

    _assert_team_access(db, team, current_user)
    return []

