from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.models.enums import CommonStatus
from app.features.employees.schemas import (
    EmployeeCreate,
    EmployeeStatusUpdate,
    EmployeeSummaryResponse,
    EmployeeDetailResponse,
)
from app.features.employees.service import (
    EmployeeService,
    EmployeeNotFoundError,
    EmployeeEmailAlreadyExistsError,
    DepartmentNotFoundError,
)

router = APIRouter(prefix="/api/v1/employees", tags=["Employees"])


@router.get(
    "",
    response_model=list[EmployeeSummaryResponse],
    summary="Browse employee directory (paginated)",
    description="Retrieve list of employees with optional search, department filter, and status filter. Accessible to all authenticated users.",
)
def list_employees(
    response: Response,
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max employees per page"),
    search: Optional[str] = Query(None, description="Search by name, employee code, or email"),
    dept_id: Optional[int] = Query(None, description="Filter by department ID"),
    status_filter: Optional[CommonStatus] = Query(None, alias="status", description="Filter by status (ACTIVE / INACTIVE)"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[EmployeeSummaryResponse]:
    summaries, total_count = EmployeeService.list_employees(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        dept_id=dept_id,
        status=status_filter,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return summaries


@router.get(
    "/{emp_id}",
    response_model=EmployeeDetailResponse,
    summary="Get employee details by ID",
    description="Retrieve comprehensive employee profile. Accessible to all authenticated users.",
)
def get_employee(
    emp_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> EmployeeDetailResponse:
    try:
        return EmployeeService.get_employee(db=db, emp_id=emp_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new employee and user account (US-04)",
    description="Onboard an employee, auto-generate EMP-XXXX code, and link user account. Restricted to HR_MANAGER and ADMIN roles.",
)
def create_employee(
    payload: EmployeeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(["HR", "HR_MANAGER", "ADMIN"])),
) -> EmployeeDetailResponse:
    client_ip = request.client.host if request.client else None
    try:
        return EmployeeService.create_employee(
            db=db,
            payload=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
    except EmployeeEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{emp_id}/status",
    response_model=EmployeeDetailResponse,
    summary="Update employee employment status (US-04)",
    description="Change status between ACTIVE and INACTIVE, and sync account login status. Restricted to HR_MANAGER and ADMIN.",
)
def update_employee_status(
    emp_id: int,
    payload: EmployeeStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(["HR", "HR_MANAGER", "ADMIN"])),
) -> EmployeeDetailResponse:
    client_ip = request.client.host if request.client else None
    try:
        return EmployeeService.update_employee_status(
            db=db,
            emp_id=emp_id,
            payload=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
