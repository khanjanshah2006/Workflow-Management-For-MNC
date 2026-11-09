import re
from typing import Optional, Tuple, List
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee
from app.models.department import Department
from app.models.user_account import UserAccount
from app.models.enums import CommonStatus


class EmployeeRepository:
    """Database repository for Employee and related UserAccount queries."""

    @staticmethod
    def get_by_id(db: Session, emp_id: int) -> Optional[Employee]:
        """Fetch employee by primary key emp_id with department eagerly loaded."""
        return (
            db.query(Employee)
            .filter(Employee.emp_id == emp_id)
            .first()
        )

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Employee]:
        """Fetch employee by email (case-insensitive)."""
        return (
            db.query(Employee)
            .filter(func.lower(Employee.email) == func.lower(email.strip()))
            .first()
        )

    @staticmethod
    def get_user_account_by_email(db: Session, email: str) -> Optional[UserAccount]:
        """Fetch user account by email to prevent duplicate accounts."""
        return (
            db.query(UserAccount)
            .filter(func.lower(UserAccount.email) == func.lower(email.strip()))
            .first()
        )

    @staticmethod
    def get_department_by_id(db: Session, dept_id: int) -> Optional[Department]:
        """Verify department exists."""
        return db.query(Department).filter(Department.dept_id == dept_id).first()

    @staticmethod
    def generate_next_emp_code(db: Session) -> str:
        """
        Auto-generates sequential employee code in format EMP-XXXX (e.g. EMP-1001).
        Finds the highest existing numeric suffix and increments by 1.
        """
        all_codes = db.query(Employee.emp_code).all()
        highest_num = 1000

        for (code,) in all_codes:
            if code and code.startswith("EMP-"):
                match = re.search(r"\d+", code.replace("EMP-", ""))
                if match:
                    try:
                        num = int(match.group())
                        if num > highest_num:
                            highest_num = num
                    except ValueError:
                        pass

        next_num = highest_num + 1
        return f"EMP-{next_num}"

    @staticmethod
    def list_employees(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        dept_id: Optional[int] = None,
        status: Optional[CommonStatus] = None,
    ) -> Tuple[List[Employee], int]:
        """
        List employees with optional search, department filter, and status filter.
        Returns a tuple of (employees_list, total_count).
        """
        query = db.query(Employee)

        # Apply search filter (name, email, or emp_code)
        if search:
            search_term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Employee.full_name).ilike(search_term),
                    func.lower(Employee.emp_code).ilike(search_term),
                    func.lower(Employee.email).ilike(search_term),
                    func.lower(Employee.designation).ilike(search_term),
                )
            )

        # Apply department filter
        if dept_id is not None:
            query = query.filter(Employee.dept_id == dept_id)

        # Apply status filter
        if status is not None:
            query = query.filter(Employee.status == status)

        total_count = query.count()

        items = (
            query.order_by(Employee.emp_id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total_count

    @staticmethod
    def create_user_account(db: Session, account: UserAccount) -> UserAccount:
        """Add UserAccount to session (flushed, not committed yet)."""
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def create_employee(db: Session, employee: Employee) -> Employee:
        """Add Employee to session (flushed, not committed yet)."""
        db.add(employee)
        db.flush()
        return employee

    @staticmethod
    def update_employee_status(
        db: Session, employee: Employee, new_status: CommonStatus
    ) -> Employee:
        """Update employee status and sync account is_active state."""
        employee.status = new_status
        if employee.account_id:
            user_account = (
                db.query(UserAccount)
                .filter(UserAccount.account_id == employee.account_id)
                .first()
            )
            if user_account:
                user_account.is_active = (new_status == CommonStatus.ACTIVE)

        db.flush()
        return employee

    @staticmethod
    def get_workload_metrics(db: Session, emp_id: int) -> dict:
        """
        Compute aggregate cross-project workload metrics for an employee (US-39):
        - active_projects_count: count of active assignments (released_on IS NULL)
        - open_tasks_count: count of non-completed tasks (status != DONE)
        - utilization_pct: calculated allocation percentage (25.0% per active project)
        """
        from app.models.project import ProjectAssignment
        from app.models.task import Task
        from app.models.enums import TaskStatus

        active_projects_count = (
            db.query(func.count(func.distinct(ProjectAssignment.project_id)))
            .filter(
                ProjectAssignment.emp_id == emp_id,
                ProjectAssignment.released_on.is_(None),
            )
            .scalar()
            or 0
        )

        open_tasks_count = (
            db.query(func.count(Task.task_id))
            .filter(
                Task.assigned_to == emp_id,
                Task.status != TaskStatus.DONE,
            )
            .scalar()
            or 0
        )

        utilization_pct = round(active_projects_count * 25.0, 2)

        return {
            "employee_id": emp_id,
            "active_projects_count": active_projects_count,
            "open_tasks_count": open_tasks_count,
            "utilization_pct": float(utilization_pct),
        }

    @staticmethod
    def get_batch_workload_metrics(db: Session, emp_ids: List[int]) -> dict:
        """
        Batch compute workload metrics for multiple employees in O(1) queries.
        Returns a dict mapping emp_id -> metrics dict.
        """
        if not emp_ids:
            return {}

        from app.models.project import ProjectAssignment
        from app.models.task import Task
        from app.models.enums import TaskStatus

        proj_counts = dict(
            db.query(
                ProjectAssignment.emp_id,
                func.count(func.distinct(ProjectAssignment.project_id)),
            )
            .filter(
                ProjectAssignment.emp_id.in_(emp_ids),
                ProjectAssignment.released_on.is_(None),
            )
            .group_by(ProjectAssignment.emp_id)
            .all()
        )

        task_counts = dict(
            db.query(
                Task.assigned_to,
                func.count(Task.task_id),
            )
            .filter(
                Task.assigned_to.in_(emp_ids),
                Task.status != TaskStatus.DONE,
            )
            .group_by(Task.assigned_to)
            .all()
        )

        result = {}
        for eid in emp_ids:
            act_proj = proj_counts.get(eid, 0)
            op_tasks = task_counts.get(eid, 0)
            result[eid] = {
                "employee_id": eid,
                "active_projects_count": act_proj,
                "open_tasks_count": op_tasks,
                "utilization_pct": float(round(act_proj * 25.0, 2)),
            }
        return result

