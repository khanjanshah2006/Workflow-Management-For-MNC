"""
Service layer for Department Management (US-05).

Coordinates business logic, transaction lifecycles, and audit logging
for Department entity operations.
"""

import json
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
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
    """
    Retrieve a department by its ID or raise DepartmentNotFoundError.

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Department primary key.

    Returns:
        Department model instance.

    Raises:
        DepartmentNotFoundError: If no department matches dept_id.
    """
    dept = repository.get_by_id(db, dept_id)
    if dept is None:
        raise DepartmentNotFoundError(dept_id)
    return dept


def list_departments(
    db: Session,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Department], int]:
    """
    Retrieve paginated departments and the total count.

    Args:
        db: Active SQLAlchemy database session.
        skip: Pagination offset.
        limit: Maximum number of records to return.

    Returns:
        Tuple of (list of Department instances, total_count).
    """
    return repository.get_all(db, skip=skip, limit=limit)


def create_department(
    db: Session,
    department_in: DepartmentCreate,
    actor_account_id: UUID | None = None,
    ip_address: str | None = None,
) -> Department:
    """
    Create a new department, validate unique name, log audit trail, and commit.

    Args:
        db: Active SQLAlchemy database session.
        department_in: Validated DepartmentCreate schema.
        actor_account_id: UUID of user account performing the action.
        ip_address: Optional IP address of client for audit.

    Returns:
        The newly created and committed Department instance.

    Raises:
        DepartmentAlreadyExistsError: If a department with this name exists.
    """
    # 1. Unique name validation
    existing = repository.get_by_name(db, department_in.name)
    if existing is not None:
        raise DepartmentAlreadyExistsError(department_in.name)

    try:
        # 2. Stage creation in repository (db.flush)
        department = repository.create(db, department_in)

        # 3. Write audit log
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

        # 4. Commit transaction
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
    """
    Update an existing department, validate name uniqueness if changed,
    log audit trail, and commit.

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Primary key of department to update.
        department_in: Validated DepartmentUpdate schema.
        actor_account_id: UUID of user account performing the action.
        ip_address: Optional IP address of client for audit.

    Returns:
        The updated and committed Department instance.

    Raises:
        DepartmentNotFoundError: If department does not exist.
        DepartmentAlreadyExistsError: If updated name conflicts with another department.
    """
    # 1. Fetch existing department
    department = repository.get_by_id(db, dept_id)
    if department is None:
        raise DepartmentNotFoundError(dept_id)

    # 2. Check name collision if name is being changed
    if department_in.name and department_in.name.lower() != department.name.lower():
        existing = repository.get_by_name(db, department_in.name)
        if existing is not None and existing.dept_id != dept_id:
            raise DepartmentAlreadyExistsError(department_in.name)

    try:
        # 3. Capture old state for audit
        old_data = {
            "name": department.name,
            "description": department.description,
        }

        # 4. Apply update
        department = repository.update(db, department, department_in)

        # 5. Capture new state and log audit
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

        # 6. Commit transaction
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
    """
    Delete a department, log audit trail, and commit.

    Args:
        db: Active SQLAlchemy database session.
        dept_id: Primary key of department to delete.
        actor_account_id: UUID of user account performing the action.
        ip_address: Optional IP address of client for audit.

    Raises:
        DepartmentNotFoundError: If department does not exist.
    """
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
