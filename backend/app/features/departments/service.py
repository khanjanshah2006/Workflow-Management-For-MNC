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
from app.core import roles
from app.models.enums import AuditAction, UserType, CommonStatus, TeamStatus
from app.features.notifications.service import NotificationService
from app.features.departments import repository
from app.features.departments.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentTeamCreate,
    DepartmentTeamUpdate,
    DepartmentTeamMemberAdd,
)


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


class TeamNameAlreadyExistsInDepartmentError(DepartmentServiceError):
    """Raised when a team with the given name already exists in the department."""

    def __init__(self, name: str, dept_id: int):
        self.name = name
        self.dept_id = dept_id
        super().__init__(f"Team with name '{name}' already exists in department {dept_id}")


class EmployeeNotFoundError(DepartmentServiceError):
    """Raised when an employee is not found."""

    def __init__(self, emp_id: int):
        self.emp_id = emp_id
        super().__init__(f"Employee with ID {emp_id} not found")


class EmployeeInactiveError(DepartmentServiceError):
    """Raised when an employee is inactive and cannot be assigned."""

    def __init__(self, emp_id: int):
        self.emp_id = emp_id
        super().__init__(f"Employee with ID {emp_id} is inactive")


class CannotRemoveLeadError(DepartmentServiceError):
    """Raised when attempting to remove the designated team lead from team members."""

    def __init__(self, team_id: int, emp_id: int):
        self.team_id = team_id
        self.emp_id = emp_id
        super().__init__(f"Cannot remove lead employee {emp_id} from team {team_id}. Change the lead first.")


class TeamMemberNotFoundError(DepartmentServiceError):
    """Raised when an employee is not found in the team."""

    def __init__(self, team_id: int, emp_id: int):
        self.team_id = team_id
        self.emp_id = emp_id
        super().__init__(f"Employee {emp_id} is not a member of team {team_id}")




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


def _record_user_account_audit_log(
    db: Session,
    action: AuditAction,
    account_id: UUID,
    old_role: str,
    new_role: str,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Helper to record an audit log entry for USER_ACCOUNT role changes."""
    audit_entry = AuditLog(
        account_id=actor_account_id,
        action=action,
        entity_name="USER_ACCOUNT",
        entity_ref_id=str(account_id),
        old_value=json.dumps({"user_type": old_role}),
        new_value=json.dumps({"user_type": new_role}),
        ip_address=ip_address,
    )
    db.add(audit_entry)
    return audit_entry


def _promote_lead_to_team_lead(
    db: Session,
    emp_id: int,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    """
    If the designated lead has an account with user_type == EMPLOYEE,
    promote them to TEAM_LEAD and record an audit log. Other roles keep their role.
    """
    emp = repository.get_employee_by_id(db, emp_id)
    if not emp or not emp.account_id:
        return

    user_acc = db.get(UserAccount, emp.account_id)
    if not user_acc:
        return

    current_role = (
        user_acc.user_type.value
        if hasattr(user_acc.user_type, "value")
        else str(user_acc.user_type)
    )
    if current_role == UserType.EMPLOYEE.value or current_role == "EMPLOYEE":
        user_acc.user_type = UserType.TEAM_LEAD
        db.add(user_acc)
        db.flush()
        _record_user_account_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            account_id=user_acc.account_id,
            old_role=current_role,
            new_role=UserType.TEAM_LEAD.value,
            actor_account_id=actor_account_id,
            ip_address=ip_address,
        )


def _demote_lead_to_employee_if_no_active_teams(
    db: Session,
    emp_id: int | None,
    exclude_team_id: int | None = None,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    """
    If the previous lead was a TEAM_LEAD and no longer leads any active team,
    demote them back to EMPLOYEE and record an audit log.
    """
    if emp_id is None:
        return

    emp = repository.get_employee_by_id(db, emp_id)
    if not emp or not emp.account_id:
        return

    user_acc = db.get(UserAccount, emp.account_id)
    if not user_acc:
        return

    current_role = (
        user_acc.user_type.value
        if hasattr(user_acc.user_type, "value")
        else str(user_acc.user_type)
    )
    if current_role != UserType.TEAM_LEAD.value and current_role != "TEAM_LEAD":
        return

    active_led_count = repository.count_active_teams_led_by_employee(
        db, emp_id=emp_id, exclude_team_id=exclude_team_id
    )
    if active_led_count == 0:
        user_acc.user_type = UserType.EMPLOYEE
        db.add(user_acc)
        db.flush()
        _record_user_account_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            account_id=user_acc.account_id,
            old_role=current_role,
            new_role=UserType.EMPLOYEE.value,
            actor_account_id=actor_account_id,
            ip_address=ip_address,
        )



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
    - Team Lead (TEAM_LEAD or EMPLOYEE account whose employee row is team.lead_emp_id) can query their own assigned team.
    - Other employees or clients attempting to query teams they do not lead receive 403 Forbidden.
    """
    user_type_val = (
        current_user.user_type.value
        if hasattr(current_user.user_type, "value")
        else str(current_user.user_type)
    ).upper()

    # HR, Admin, PM have unrestricted read access to team rosters
    if user_type_val in (roles.HR, roles.ADMIN, roles.PM):
        return

    # Team Lead / Employee must be the designated Team Lead for this specific team
    if user_type_val in (roles.TEAM_LEAD, roles.EMPLOYEE):
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


# ==========================================
# Department Team Management Services (US-05)
# ==========================================


def create_department_team(
    db: Session,
    dept_id: int,
    team_in: DepartmentTeamCreate,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> tuple[Team, Employee, list[Employee]]:
    """
    Create a new team under department dept_id.
    - 404 if department or any employee missing.
    - 400 if any employee inactive.
    - 409 if duplicate team name in department.
    - Lead automatically added to team members.
    - Lead promoted to TEAM_LEAD if account is EMPLOYEE.
    - Notifications sent via NotificationService.
    - Single commit per request.
    """
    # 1. 404 checks: department, lead, and members must exist
    dept = repository.get_by_id(db, dept_id)
    if dept is None:
        raise DepartmentNotFoundError(dept_id)

    lead_emp = repository.get_employee_by_id(db, team_in.lead_emp_id)
    if lead_emp is None:
        raise EmployeeNotFoundError(team_in.lead_emp_id)

    members_map = {}
    for mid in team_in.member_emp_ids:
        m = repository.get_employee_by_id(db, mid)
        if m is None:
            raise EmployeeNotFoundError(mid)
        members_map[mid] = m

    # 2. 400 checks: lead and all members must be ACTIVE
    if lead_emp.status != CommonStatus.ACTIVE:
        raise EmployeeInactiveError(lead_emp.emp_id)

    for mid, m in members_map.items():
        if m.status != CommonStatus.ACTIVE:
            raise EmployeeInactiveError(m.emp_id)

    # 3. 409 check: unique team name per department (case-insensitive)
    existing = repository.get_team_by_name_in_dept(db, dept_id, team_in.name)
    if existing is not None:
        raise TeamNameAlreadyExistsInDepartmentError(team_in.name, dept_id)

    try:
        # 4. Create team
        team = repository.create_team(db, dept_id, team_in)

        # 5. Lead membership: lead must be active employee, and is added as a member automatically
        all_emp_ids = [team_in.lead_emp_id]
        for mid in team_in.member_emp_ids:
            if mid not in all_emp_ids:
                all_emp_ids.append(mid)

        repository.add_team_members(db, team.team_id, all_emp_ids)

        # 6. Lead promotion
        _promote_lead_to_team_lead(
            db,
            emp_id=team_in.lead_emp_id,
            actor_account_id=actor_account_id,
            ip_address=ip_address,
        )

        # 7. Notifications
        if lead_emp.account_id:
            NotificationService.create_notification(
                db=db,
                user_id=lead_emp.account_id,
                type="TEAM_LEAD_ASSIGNED",
                title="Team Lead Assignment",
                message=f"You are now team lead of {team.name}",
            )

        for mid, m in members_map.items():
            if m.account_id:
                NotificationService.create_notification(
                    db=db,
                    user_id=m.account_id,
                    type="TEAM_MEMBER_ADDED",
                    title="Team Membership",
                    message=f"You joined {team.name}",
                )
            if lead_emp.account_id and mid != lead_emp.emp_id:
                NotificationService.create_notification(
                    db=db,
                    user_id=lead_emp.account_id,
                    type="TEAM_MEMBER_ADDED",
                    title="New Team Member",
                    message=f"{m.full_name} joined {team.name}",
                )

        _record_audit_log(
            db=db,
            action=AuditAction.CREATE,
            dept_id=dept_id,
            account_id=actor_account_id,
            new_value={"team_id": team.team_id, "name": team.name, "lead_emp_id": team.lead_emp_id},
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(team)

        all_members = repository.get_all_members_for_team(db, team.team_id)
        return team, lead_emp, all_members
    except Exception:
        db.rollback()
        raise


def list_department_teams(
    db: Session,
    dept_id: int,
    include_disbanded: bool = False,
) -> list[tuple[Team, str | None, int]]:
    """List teams in department. 404 if department not found."""
    dept = repository.get_by_id(db, dept_id)
    if dept is None:
        raise DepartmentNotFoundError(dept_id)
    return repository.get_department_teams(db, dept_id, include_disbanded=include_disbanded)


def update_team(
    db: Session,
    team_id: int,
    team_in: DepartmentTeamUpdate,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> tuple[Team, Employee | None, list[Employee]]:
    """
    Partial update of name, description, lead_emp_id and status.
    Setting status=DISBANDED runs the lead demotion check.
    """
    team = repository.get_team_by_id(db, team_id)
    if team is None:
        raise TeamNotFoundError(team_id)

    new_lead = None
    if team_in.lead_emp_id is not None and team_in.lead_emp_id != team.lead_emp_id:
        new_lead = repository.get_employee_by_id(db, team_in.lead_emp_id)
        if new_lead is None:
            raise EmployeeNotFoundError(team_in.lead_emp_id)
        if new_lead.status != CommonStatus.ACTIVE:
            raise EmployeeInactiveError(new_lead.emp_id)

    if team_in.name and team.dept_id is not None:
        existing = repository.get_team_by_name_in_dept(
            db, dept_id=team.dept_id, name=team_in.name, exclude_team_id=team_id
        )
        if existing is not None:
            raise TeamNameAlreadyExistsInDepartmentError(team_in.name, team.dept_id)

    prev_lead_id = team.lead_emp_id
    prev_status = team.status
    old_data = {
        "name": team.name,
        "description": team.description,
        "lead_emp_id": team.lead_emp_id,
        "status": team.status.value if hasattr(team.status, "value") else str(team.status),
    }

    try:
        if team_in.name is not None:
            team.name = team_in.name.strip()
        if team_in.description is not None:
            team.description = team_in.description.strip() if team_in.description else None
        if team_in.lead_emp_id is not None:
            team.lead_emp_id = team_in.lead_emp_id
        if team_in.status is not None:
            team.status = team_in.status

        db.flush()

        # Handle lead change
        if team_in.lead_emp_id is not None and team_in.lead_emp_id != prev_lead_id:
            repository.add_team_members(db, team.team_id, [team.lead_emp_id])
            if team.status == TeamStatus.ACTIVE:
                _promote_lead_to_team_lead(
                    db,
                    emp_id=team.lead_emp_id,
                    actor_account_id=actor_account_id,
                    ip_address=ip_address,
                )
            _demote_lead_to_employee_if_no_active_teams(
                db,
                emp_id=prev_lead_id,
                actor_account_id=actor_account_id,
                ip_address=ip_address,
            )
            if new_lead and new_lead.account_id:
                NotificationService.create_notification(
                    db=db,
                    user_id=new_lead.account_id,
                    type="TEAM_LEAD_ASSIGNED",
                    title="Team Lead Assignment",
                    message=f"You are now team lead of {team.name}",
                )

        # Handle status change to DISBANDED
        if team_in.status == TeamStatus.DISBANDED and prev_status != TeamStatus.DISBANDED:
            _demote_lead_to_employee_if_no_active_teams(
                db,
                emp_id=team.lead_emp_id,
                actor_account_id=actor_account_id,
                ip_address=ip_address,
            )

        new_data = {
            "name": team.name,
            "description": team.description,
            "lead_emp_id": team.lead_emp_id,
            "status": team.status.value if hasattr(team.status, "value") else str(team.status),
        }
        if team.dept_id:
            _record_audit_log(
                db=db,
                action=AuditAction.UPDATE,
                dept_id=team.dept_id,
                account_id=actor_account_id,
                old_value=old_data,
                new_value=new_data,
                ip_address=ip_address,
            )

        db.commit()
        db.refresh(team)

        lead = repository.get_employee_by_id(db, team.lead_emp_id) if team.lead_emp_id else None
        all_members = repository.get_all_members_for_team(db, team.team_id)
        return team, lead, all_members
    except Exception:
        db.rollback()
        raise


def add_team_members(
    db: Session,
    team_id: int,
    members_in: DepartmentTeamMemberAdd,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> tuple[Team, Employee | None, list[Employee]]:
    """
    Idempotently add members to team.
    404 if team or employee missing.
    400 if employee inactive.
    """
    team = repository.get_team_by_id(db, team_id)
    if team is None:
        raise TeamNotFoundError(team_id)

    employees = []
    for emp_id in members_in.emp_ids:
        emp = repository.get_employee_by_id(db, emp_id)
        if emp is None:
            raise EmployeeNotFoundError(emp_id)
        if emp.status != CommonStatus.ACTIVE:
            raise EmployeeInactiveError(emp_id)
        employees.append(emp)

    try:
        newly_added_ids = repository.add_team_members(db, team_id, members_in.emp_ids)
        lead_emp = repository.get_employee_by_id(db, team.lead_emp_id) if team.lead_emp_id else None

        for emp in employees:
            if emp.emp_id in newly_added_ids:
                if emp.account_id:
                    NotificationService.create_notification(
                        db=db,
                        user_id=emp.account_id,
                        type="TEAM_MEMBER_ADDED",
                        title="Team Membership",
                        message=f"You joined {team.name}",
                    )
                if lead_emp and lead_emp.account_id and emp.emp_id != lead_emp.emp_id:
                    NotificationService.create_notification(
                        db=db,
                        user_id=lead_emp.account_id,
                        type="TEAM_MEMBER_ADDED",
                        title="New Team Member",
                        message=f"{emp.full_name} joined {team.name}",
                    )

        db.commit()
        db.refresh(team)

        all_members = repository.get_all_members_for_team(db, team_id)
        return team, lead_emp, all_members
    except Exception:
        db.rollback()
        raise


def remove_team_member(
    db: Session,
    team_id: int,
    emp_id: int,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Remove an employee from team members.
    404 if team or employee missing.
    409 if employee is the designated team lead.
    """
    team = repository.get_team_by_id(db, team_id)
    if team is None:
        raise TeamNotFoundError(team_id)

    emp = repository.get_employee_by_id(db, emp_id)
    if emp is None:
        raise EmployeeNotFoundError(emp_id)

    if team.lead_emp_id == emp_id:
        raise CannotRemoveLeadError(team_id, emp_id)

    if not repository.is_team_member(db, team_id, emp_id):
        raise TeamMemberNotFoundError(team_id, emp_id)

    try:
        repository.remove_team_member(db, team_id, emp_id)
        db.commit()
    except Exception:
        db.rollback()
        raise


