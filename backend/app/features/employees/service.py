import secrets
import string
from typing import Optional, Tuple, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.user_account import UserAccount
from app.models.department import Department
from app.models.enums import CommonStatus, UserType, AuditAction
from app.core.security import hash_password
from app.core.audit import write_audit_log
from app.features.employees.repository import EmployeeRepository
from app.features.employees.schemas import (
    EmployeeCreate,
    EmployeeStatusUpdate,
    EmployeeSummaryResponse,
    EmployeeDetailResponse,
    DepartmentSummary,
)


class EmployeeServiceError(Exception):
    """Base exception for employee service."""
    pass


class EmployeeNotFoundError(EmployeeServiceError):
    """Raised when employee does not exist."""
    def __init__(self, emp_id: int):
        self.emp_id = emp_id
        super().__init__(f"Employee with ID {emp_id} not found")


class EmployeeEmailAlreadyExistsError(EmployeeServiceError):
    """Raised when employee or account email is already registered."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"An employee or user account with email '{email}' already exists")


class DepartmentNotFoundError(EmployeeServiceError):
    """Raised when department ID does not exist."""
    def __init__(self, dept_id: int):
        self.dept_id = dept_id
        super().__init__(f"Department with ID {dept_id} not found")


def _generate_default_password(length: int = 10) -> str:
    """Generate a random temporary password (e.g. Temp@x9Kq2!)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "Temp@" + "".join(secrets.choice(alphabet) for _ in range(length))


class EmployeeService:
    """Business logic for Employee Directory and HR Onboarding (US-04)."""

    @staticmethod
    def create_employee(
        db: Session,
        payload: EmployeeCreate,
        actor_account_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> EmployeeDetailResponse:
        """
        Onboard a new employee in an atomic transaction:
        1. Checks unique email in Employee and UserAccount tables.
        2. Validates department if dept_id is provided.
        3. Creates USER_ACCOUNT with hashed temporary password.
        4. Generates unique sequential EMP-XXXX code.
        5. Creates EMPLOYEE linked to the USER_ACCOUNT.
        6. Logs state-changing action to AUDIT_LOG.
        """
        email_clean = payload.email.strip().lower()

        # Check existing employee or account email
        if EmployeeRepository.get_by_email(db, email_clean):
            raise EmployeeEmailAlreadyExistsError(email_clean)
        if EmployeeRepository.get_user_account_by_email(db, email_clean):
            raise EmployeeEmailAlreadyExistsError(email_clean)

        # Validate department
        department_obj: Optional[Department] = None
        if payload.dept_id:
            department_obj = EmployeeRepository.get_department_by_id(db, payload.dept_id)
            if not department_obj:
                raise DepartmentNotFoundError(payload.dept_id)

        # Initial password
        temp_password = payload.initial_password or _generate_default_password()
        hashed_pwd = hash_password(temp_password)

        # 1. Create UserAccount
        user_account = UserAccount(
            email=email_clean,
            password_hash=hashed_pwd,
            user_type=payload.user_type or UserType.EMPLOYEE,
            is_active=True,
        )
        EmployeeRepository.create_user_account(db, user_account)

        # 2. Generate emp_code
        emp_code = EmployeeRepository.generate_next_emp_code(db)

        # 3. Create Employee
        new_employee = Employee(
            account_id=user_account.account_id,
            dept_id=payload.dept_id,
            emp_code=emp_code,
            full_name=payload.full_name.strip(),
            email=email_clean,
            phone=payload.phone.strip() if payload.phone else None,
            designation=payload.designation.strip(),
            date_of_joining=payload.date_of_joining,
            status=CommonStatus.ACTIVE,
        )
        EmployeeRepository.create_employee(db, new_employee)

        # Commit atomic transaction
        db.commit()
        db.refresh(new_employee)

        # 4. Audit Log
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="EMPLOYEE",
            entity_ref_id=str(new_employee.emp_id),
            account_id=actor_account_id,
            new_value={
                "emp_code": emp_code,
                "email": email_clean,
                "full_name": new_employee.full_name,
                "designation": new_employee.designation,
                "dept_id": new_employee.dept_id,
            },
            ip_address=ip_address,
        )

        dept_summary = None
        if department_obj:
            dept_summary = DepartmentSummary(dept_id=department_obj.dept_id, name=department_obj.name)

        return EmployeeDetailResponse(
            emp_id=new_employee.emp_id,
            account_id=new_employee.account_id,
            emp_code=new_employee.emp_code,
            full_name=new_employee.full_name,
            email=new_employee.email,
            phone=new_employee.phone,
            designation=new_employee.designation,
            dept_id=new_employee.dept_id,
            department=dept_summary,
            status=new_employee.status,
            date_of_joining=new_employee.date_of_joining,
            initial_password=temp_password,
        )

    @staticmethod
    def list_employees(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        dept_id: Optional[int] = None,
        status: Optional[CommonStatus] = None,
    ) -> Tuple[List[EmployeeSummaryResponse], int]:
        """List employees with filters and pagination."""
        employees, total = EmployeeRepository.list_employees(
            db=db, skip=skip, limit=limit, search=search, dept_id=dept_id, status=status
        )

        # Pre-fetch department names
        dept_ids = {e.dept_id for e in employees if e.dept_id}
        dept_map = {}
        if dept_ids:
            departments = db.query(Department).filter(Department.dept_id.in_(dept_ids)).all()
            dept_map = {d.dept_id: d.name for d in departments}

        summaries = [
            EmployeeSummaryResponse(
                emp_id=e.emp_id,
                emp_code=e.emp_code,
                full_name=e.full_name,
                email=e.email,
                phone=e.phone,
                designation=e.designation,
                dept_id=e.dept_id,
                department_name=dept_map.get(e.dept_id),
                status=e.status,
                date_of_joining=e.date_of_joining,
            )
            for e in employees
        ]

        return summaries, total

    @staticmethod
    def get_employee(db: Session, emp_id: int) -> EmployeeDetailResponse:
        """Fetch employee details by ID."""
        employee = EmployeeRepository.get_by_id(db, emp_id)
        if not employee:
            raise EmployeeNotFoundError(emp_id)

        dept_summary = None
        if employee.dept_id:
            dept = EmployeeRepository.get_department_by_id(db, employee.dept_id)
            if dept:
                dept_summary = DepartmentSummary(dept_id=dept.dept_id, name=dept.name)

        return EmployeeDetailResponse(
            emp_id=employee.emp_id,
            account_id=employee.account_id,
            emp_code=employee.emp_code,
            full_name=employee.full_name,
            email=employee.email,
            phone=employee.phone,
            designation=employee.designation,
            dept_id=employee.dept_id,
            department=dept_summary,
            status=employee.status,
            date_of_joining=employee.date_of_joining,
            initial_password=None,
        )

    @staticmethod
    def update_employee_status(
        db: Session,
        emp_id: int,
        payload: EmployeeStatusUpdate,
        actor_account_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> EmployeeDetailResponse:
        """
        Soft activate or deactivate an employee and sync user account is_active state.
        Audits the status transition.
        """
        employee = EmployeeRepository.get_by_id(db, emp_id)
        if not employee:
            raise EmployeeNotFoundError(emp_id)

        old_status = employee.status
        EmployeeRepository.update_employee_status(db, employee, payload.status)
        db.commit()
        db.refresh(employee)

        # Audit log status change
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="EMPLOYEE",
            entity_ref_id=str(employee.emp_id),
            account_id=actor_account_id,
            old_value={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
            new_value={"status": payload.status.value if hasattr(payload.status, "value") else str(payload.status)},
            ip_address=ip_address,
        )

        return EmployeeService.get_employee(db, emp_id)
