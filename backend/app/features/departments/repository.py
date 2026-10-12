"""
Repository layer for Department Management (US-05).

Handles database persistence and queries for the DEPARTMENT entity.
Business validation, RBAC enforcement, and audit logging are handled
in the service/router layers per API architecture patterns.

Database & Model Foundation:
- Canonical ORM Model: `Department` in `app.models.department`
  - Columns:
    - `dept_id`: int, primary key (autoincrement)
    - `name`: str (150), unique, indexed, non-nullable
    - `description`: str | None, nullable
    - `created_at`: datetime, default func.now()
- Database Session: `Session` from `sqlalchemy.orm`, injected via
  `get_db` dependency in `app.db.session`.
- Transaction boundary: The repository executes queries and calls `db.flush()`
  to allocate primary keys and stage changes. The service layer retains full
  ownership of `db.commit()` alongside audit logging.
- Structural Note: In the finalized schema, Employee has `dept_id` referencing
  Department. The Team model has no `dept_id` foreign key.
"""

from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from .schemas import DepartmentCreate, DepartmentUpdate


def get_by_id(db: Session, dept_id: int) -> Department | None:
    """
    Retrieve a single department by its primary key (dept_id).

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Primary key of the department.

    Returns:
        The Department model instance if found, otherwise None.
    """
    return db.get(Department, dept_id)


def get_by_name(db: Session, name: str) -> Department | None:
    """
    Retrieve a single department by case-insensitive name match.
    Provides the lookup query used by the service layer for duplicate-name validation.

    Args:
        db: Active SQLAlchemy database session.
        name: Name of the department to search for.

    Returns:
        The matching Department model instance if found, otherwise None.
    """
    cleaned_name = name.strip()
    stmt = select(Department).where(func.lower(Department.name) == cleaned_name.lower())
    return db.scalars(stmt).first()


def get_all(
    db: Session,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Department], int]:
    """
    Retrieve paginated departments along with total record count.

    Args:
        db: Active SQLAlchemy database session.
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.

    Returns:
        A tuple of (list of Department model instances, total_count).
    """
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
    """
    Delete an existing Department record from the database.
    Calls db.flush() to stage deletion without committing the transaction.

    Args:
        db: Active SQLAlchemy database session.
        department: Department model instance to delete.
    """
    db.delete(department)
    db.flush()
