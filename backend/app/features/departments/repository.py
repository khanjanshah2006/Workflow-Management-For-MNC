"""
Repository layer for Department Management (US-05).

Handles database persistence and queries for the DEPARTMENT entity.
Business validation, RBAC enforcement, and audit logging are intentionally
excluded here and handled in the service/router layers.

Integration Requirements (Sprint 1 Foundation / Issue 1):
- Expected ORM Models: `Department` and `Team` defined in `app.models.org`
  per `.agent/skills/project-structure/SKILL.md` and `docs/database/ER_Diagram.md`.
  Fields on Department:
    - `dept_id`: int, primary key (autoincrement)
    - `name`: str, unique, not null
    - `description`: str | None, nullable
    - `created_at`: datetime, default utcnow
  Foreign Key on Team:
    - `department_id` (or `dept_id`): int, foreign key referencing Department.dept_id
- Expected Session Interface: `Session` from `sqlalchemy.orm`, injected via
  `get_db` dependency in `core/database.py`.
- Transaction boundary: The repository executes queries and calls `db.flush()`
  to allocate primary keys and stage changes. The service layer retains full
  ownership of `db.commit()` alongside audit logging (`write_audit_log`).
"""

from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .schemas import DepartmentCreate, DepartmentUpdate

# Import canonical models defined by Issue 1 (Database & Models infrastructure)
try:
    from app.models.org import Department, Team  # type: ignore
except ImportError:
    try:
        from backend.app.models.org import Department, Team  # type: ignore
    except ImportError:
        Department = None  # type: ignore
        Team = None  # type: ignore


def _ensure_models_available() -> None:
    """
    Ensure the actual Department model is available before executing queries.
    Raises RuntimeError instead of returning fake data or empty results.
    """
    if Department is None:
        raise RuntimeError(
            "Department database model is not available. Awaiting Issue 1 / Sprint 1 "
            "Foundation to establish database infrastructure and 'app.models.org.Department'."
        )


def get_by_id(db: Session, dept_id: int) -> Any | None:
    """
    Retrieve a single department by its primary key (dept_id).

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Primary key of the department.

    Returns:
        The Department model instance if found, otherwise None.
    """
    _ensure_models_available()
    return db.get(Department, dept_id)


def get_by_name(db: Session, name: str) -> Any | None:
    """
    Retrieve a single department by case-insensitive name match.
    Provides the lookup query used by the service layer for duplicate-name validation.

    Args:
        db: Active SQLAlchemy database session.
        name: Name of the department to search for.

    Returns:
        The matching Department model instance if found, otherwise None.
    """
    _ensure_models_available()
    cleaned_name = name.strip()
    stmt = select(Department).where(func.lower(Department.name) == cleaned_name.lower())
    return db.scalars(stmt).first()


def get_by_id_with_team_count(db: Session, dept_id: int) -> tuple[Any, int] | None:
    """
    Retrieve a department along with its aggregated team count in a single query.

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Primary key of the department.

    Returns:
        A tuple of (department_instance, team_count) if found, otherwise None.
    """
    _ensure_models_available()

    team_dept_col = getattr(Team, "department_id", getattr(Team, "dept_id", None)) if Team else None

    if team_dept_col is not None:
        stmt = (
            select(Department, func.count(Team.team_id).label("team_count"))
            .outerjoin(Team, team_dept_col == Department.dept_id)
            .where(Department.dept_id == dept_id)
            .group_by(Department.dept_id)
        )
        row = db.execute(stmt).first()
        if row is None:
            return None
        return row[0], row[1]

    # Fallback to model relationship if configured without direct Team column reference
    department = db.get(Department, dept_id)
    if department is None:
        return None
    team_count = len(getattr(department, "teams", []))
    return department, team_count


def get_all(
    db: Session,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[tuple[Any, int]], int]:
    """
    Retrieve paginated departments along with aggregated team counts and total record count.
    Avoids N+1 queries by aggregating team counts in an outer join.

    Args:
        db: Active SQLAlchemy database session.
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.

    Returns:
        A tuple of (list of (department_instance, team_count), total_count).
    """
    _ensure_models_available()

    # Query 1: Total count of departments
    total_count = db.scalar(select(func.count(Department.dept_id))) or 0
    if total_count == 0:
        return [], 0

    # Query 2: Paginated fetch with aggregated team count in a single query (no N+1)
    team_dept_col = getattr(Team, "department_id", getattr(Team, "dept_id", None)) if Team else None

    if team_dept_col is not None:
        stmt = (
            select(Department, func.count(Team.team_id).label("team_count"))
            .outerjoin(Team, team_dept_col == Department.dept_id)
            .group_by(Department.dept_id)
            .order_by(Department.dept_id.asc())
            .offset(skip)
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        items = [(row[0], row[1]) for row in rows]
        return items, total_count

    # Fallback to relationship attribute if Team table is unmapped
    stmt = (
        select(Department)
        .order_by(Department.dept_id.asc())
        .offset(skip)
        .limit(limit)
    )
    departments = db.scalars(stmt).all()
    items = [(dept, len(getattr(dept, "teams", []))) for dept in departments]
    return items, total_count


def create(db: Session, department_in: DepartmentCreate) -> Any:
    """
    Instantiate and persist a new Department record.
    Calls db.flush() and db.refresh() to populate generated fields (dept_id, created_at).
    Does NOT call commit(); transaction ownership belongs strictly to the service layer.

    Args:
        db: Active SQLAlchemy database session.
        department_in: Validated DepartmentCreate schema.

    Returns:
        The newly created Department model instance.
    """
    _ensure_models_available()

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
    department: Any,
    department_in: DepartmentUpdate | dict[str, Any],
) -> Any:
    """
    Update an existing Department record with new field values.
    Applies only provided fields (supports partial updates).
    Calls db.flush() and db.refresh() to stage changes without committing the transaction.

    Args:
        db: Active SQLAlchemy database session.
        department: Existing Department model instance.
        department_in: Validated DepartmentUpdate schema or dictionary of changes.

    Returns:
        The updated Department model instance.
    """
    _ensure_models_available()

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
