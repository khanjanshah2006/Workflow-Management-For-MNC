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
