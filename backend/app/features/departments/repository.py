from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from .schemas import DepartmentCreate, DepartmentUpdate


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
