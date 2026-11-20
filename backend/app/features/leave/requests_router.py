"""Leave requests, balances, cancellation and history router (US-16, US-40, S4-BE-1)."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core import scope
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.schemas import (
    EmployeeLeaveBalanceResponse,
    LeaveBalanceOut,
    LeaveRequestCreate,
    LeaveRequestOut,
    PaginatedLeaveRequestsOut,
)
from app.features.leave.service import LeaveService
from app.models.employee import Employee
from app.models.enums import LeaveStatus, UserType
from app.models.user_account import UserAccount

router = APIRouter()


def get_today() -> date:
    """Return today's date; injectable for testing."""
    return date.today()


@router.post(
    "/requests",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new leave request (US-16)",
)
def submit_leave_request(
    payload: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
    today: date = Depends(get_today),
) -> LeaveRequestOut:
    """
    Submit a leave request.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    Requires an active employee profile.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return LeaveService.submit_leave_request(
        db=db,
        current_user=current_user,
        data=payload,
        today=today,
    )


@router.get(
    "/requests/my",
    response_model=PaginatedLeaveRequestsOut,
    status_code=status.HTTP_200_OK,
    summary="List leave history for current user (US-16)",
)
def get_my_leave_requests(
    status_filter: Optional[LeaveStatus] = Query(None, alias="status", description="Filter by status"),
    year: Optional[int] = Query(None, description="Filter by start date calendar year"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PaginatedLeaveRequestsOut:
    """
    Retrieve leave history for the authenticated employee.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return LeaveService.list_my_leave_history(
        db=db,
        current_user=current_user,
        status_filter=status_filter,
        year=year,
        page=page,
        limit=limit,
    )


@router.put(
    "/requests/{id}/cancel",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending leave request (US-16)",
)
def cancel_leave_request(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> LeaveRequestOut:
    """
    Cancel an existing PENDING leave request owned by the authenticated employee.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return LeaveService.cancel_leave_request(
        db=db,
        current_user=current_user,
        leave_id=id,
    )


# NOTE: /balance/me MUST be declared BEFORE /balance/{employee_id}
@router.get(
    "/balance/me",
    response_model=EmployeeLeaveBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my leave balance (US-16)",
)
def get_my_leave_balance(
    year: Optional[int] = Query(None, description="Calendar year (defaults to current year)"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> EmployeeLeaveBalanceResponse:
    """
    Return year-wise leave balances for the authenticated employee.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    emp = scope.resolve_employee(db, current_user)
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No employee profile linked to this account",
        )
    return LeaveService.get_employee_leave_balances(
        db=db,
        emp_id=emp.emp_id,
        year=year,
    )


@router.get(
    "/balance/{employee_id}",
    response_model=EmployeeLeaveBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get leave balance for an employee (US-16)",
)
def get_employee_leave_balance(
    employee_id: int,
    year: Optional[int] = Query(None, description="Calendar year (defaults to current year)"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> EmployeeLeaveBalanceResponse:
    """
    Return year-wise leave balances for a specific employee.
    Authorization rules:
    - EMPLOYEE: own balance only.
    - TEAM_LEAD: own balance or an employee belonging to an active team they lead.
    - HR / ADMIN / SYSTEM_ADMIN: any employee.
    - Other roles: 403 Forbidden.
    - Unknown employee: 404 Not Found.
    """
    user_type = getattr(current_user.user_type, "value", str(current_user.user_type)).upper()
    allowed_types = {
        UserType.EMPLOYEE.value,
        UserType.TEAM_LEAD.value,
        UserType.HR.value,
        UserType.ADMIN.value,
        UserType.SYSTEM_ADMIN.value,
    }
    if user_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden",
        )

    target_emp = db.get(Employee, employee_id)

    if user_type == UserType.EMPLOYEE.value:
        current_emp = scope.resolve_employee(db, current_user)
        if current_emp is None or current_emp.emp_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You can only view your own leave balance",
            )
        if target_emp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

    elif user_type == UserType.TEAM_LEAD.value:
        current_emp = scope.resolve_employee(db, current_user)
        if current_emp is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this account",
            )
        if target_emp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )
        if current_emp.emp_id != employee_id and not scope.is_team_lead_of(db, current_emp.emp_id, employee_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You can only view balances of members of teams you lead",
            )

    else:
        # HR, ADMIN, SYSTEM_ADMIN
        if target_emp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

    return LeaveService.get_employee_leave_balances(
        db=db,
        emp_id=employee_id,
        year=year,
    )
