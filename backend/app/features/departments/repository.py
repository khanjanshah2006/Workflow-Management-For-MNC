from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team, TeamMember
from app.models.enums import CommonStatus, TeamStatus
from .schemas import DepartmentCreate, DepartmentUpdate, DepartmentTeamCreate, DepartmentTeamUpdate


def get_by_id(db: Session, dept_id: int) -> Department | None:
    return db.get(Department, dept_id)


def get_by_name(db: Session, name: str) -> Department | None:
    cleaned_name = name.strip()
    stmt = select(Department).where(func.lower(Department.name) == cleaned_name.lower())
    return db.scalars(stmt).first()


def get_all(
    db: Session,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Department], int]:
    total_count = db.scalar(select(func.count(Department.dept_id))) or 0
    if total_count == 0:
        return [], 0

    stmt = (
        select(Department)
        .order_by(Department.dept_id.asc())
        .offset(skip)
        .limit(limit)
    )
    departments = list(db.scalars(stmt).all())
    return departments, total_count


def create(db: Session, department_in: DepartmentCreate) -> Department:
    department = Department(
        name=department_in.name,
        description=department_in.description,
    )
    db.add(department)
    db.flush()
    db.refresh(department)
    return department


def update(
    db: Session,
    department: Department,
    department_in: DepartmentUpdate | dict[str, Any],
) -> Department:
    update_data = (
        department_in.model_dump(exclude_unset=True)
        if isinstance(department_in, DepartmentUpdate)
        else department_in
    )

    for field, value in update_data.items():
        if hasattr(department, field):
            setattr(department, field, value)

    db.add(department)
    db.flush()
    db.refresh(department)
    return department


def delete(db: Session, department: Department) -> None:
    db.delete(department)
    db.flush()


# ==========================================
# Team Member Repository Functions (US-37)
# ==========================================


def get_team_by_id(db: Session, team_id: int) -> Team | None:
    """Fetch a team record by primary key."""
    return db.get(Team, team_id)


def get_active_members_for_team(db: Session, team_id: int) -> list[Employee]:
    """
    Query all ACTIVE employees assigned to the given team via team_member join.
    Uses parameterized SQLAlchemy ORM select query (SQLi safe).
    """
    stmt = (
        select(Employee)
        .join(TeamMember, TeamMember.emp_id == Employee.emp_id)
        .where(
            TeamMember.team_id == team_id,
            Employee.status == CommonStatus.ACTIVE,
        )
        .order_by(Employee.emp_id.asc())
    )
    return list(db.scalars(stmt).all())


def get_all_members_for_team(db: Session, team_id: int) -> list[Employee]:
    """Query all employees (any status) assigned to team via team_member join."""
    stmt = (
        select(Employee)
        .join(TeamMember, TeamMember.emp_id == Employee.emp_id)
        .where(TeamMember.team_id == team_id)
        .order_by(Employee.emp_id.asc())
    )
    return list(db.scalars(stmt).all())


def get_team_by_name_in_dept(
    db: Session,
    dept_id: int,
    name: str,
    exclude_team_id: int | None = None,
) -> Team | None:
    """Check case-insensitive duplicate team name in a given department."""
    cleaned = name.strip()
    stmt = select(Team).where(
        Team.dept_id == dept_id,
        func.lower(Team.name) == cleaned.lower(),
    )
    if exclude_team_id is not None:
        stmt = stmt.where(Team.team_id != exclude_team_id)
    return db.scalars(stmt).first()


def get_department_teams(
    db: Session,
    dept_id: int,
    include_disbanded: bool = False,
) -> list[tuple[Team, str | None, int]]:
    """
    List teams belonging to dept_id.
    Returns tuples of (Team, lead_full_name, member_count).
    """
    stmt = select(Team).where(Team.dept_id == dept_id)
    if not include_disbanded:
        stmt = stmt.where(Team.status == TeamStatus.ACTIVE)
    stmt = stmt.order_by(Team.team_id.asc())
    teams = list(db.scalars(stmt).all())

    results = []
    for t in teams:
        lead_name = None
        if t.lead_emp_id:
            lead = db.get(Employee, t.lead_emp_id)
            if lead:
                lead_name = lead.full_name
        member_cnt = db.scalar(
            select(func.count(TeamMember.team_member_id)).where(TeamMember.team_id == t.team_id)
        ) or 0
        results.append((t, lead_name, member_cnt))
    return results


def get_employee_by_id(db: Session, emp_id: int) -> Employee | None:
    """Fetch employee by PK."""
    return db.get(Employee, emp_id)


def get_employees_by_ids(db: Session, emp_ids: list[int]) -> list[Employee]:
    """Fetch list of employees matching the given IDs."""
    if not emp_ids:
        return []
    stmt = select(Employee).where(Employee.emp_id.in_(emp_ids))
    return list(db.scalars(stmt).all())


def count_active_teams_led_by_employee(
    db: Session,
    emp_id: int,
    exclude_team_id: int | None = None,
) -> int:
    """Count active teams where emp_id is the lead."""
    stmt = select(func.count(Team.team_id)).where(
        Team.lead_emp_id == emp_id,
        Team.status == TeamStatus.ACTIVE,
    )
    if exclude_team_id is not None:
        stmt = stmt.where(Team.team_id != exclude_team_id)
    return db.scalar(stmt) or 0


def create_team(db: Session, dept_id: int, team_in: DepartmentTeamCreate) -> Team:
    """Create a new team under a department."""
    team = Team(
        dept_id=dept_id,
        name=team_in.name.strip(),
        description=team_in.description.strip() if team_in.description else None,
        lead_emp_id=team_in.lead_emp_id,
        status=TeamStatus.ACTIVE,
    )
    db.add(team)
    db.flush()
    db.refresh(team)
    return team


def add_team_members(db: Session, team_id: int, emp_ids: list[int]) -> list[int]:
    """
    Idempotently add members to team_member.
    Returns list of newly added employee IDs.
    """
    if not emp_ids:
        return []

    stmt = select(TeamMember.emp_id).where(TeamMember.team_id == team_id)
    existing_emp_ids = set(db.scalars(stmt).all())

    newly_added = []
    for emp_id in emp_ids:
        if emp_id not in existing_emp_ids:
            tm = TeamMember(team_id=team_id, emp_id=emp_id)
            db.add(tm)
            existing_emp_ids.add(emp_id)
            newly_added.append(emp_id)

    db.flush()
    return newly_added


def remove_team_member(db: Session, team_id: int, emp_id: int) -> bool:
    """Remove an employee from team_member. Returns True if removed, False if not present."""
    stmt = select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.emp_id == emp_id)
    tm = db.scalars(stmt).first()
    if tm:
        db.delete(tm)
        db.flush()
        return True
    return False


def is_team_member(db: Session, team_id: int, emp_id: int) -> bool:
    """Check if employee is member of team."""
    stmt = select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.emp_id == emp_id)
    return db.scalars(stmt).first() is not None


