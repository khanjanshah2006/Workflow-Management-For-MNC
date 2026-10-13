from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.departments import service
from app.features.departments.dependencies import (
    get_current_user,
    require_roles,
)
from app.models.user_account import UserAccount
from app.features.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)

router = APIRouter(prefix="/api/v1/departments", tags=["Departments"])


@router.get(
    "",
    response_model=list[DepartmentResponse],
    summary="List all departments (paginated)",
    description="Retrieve departments with pagination. Accessible to all authenticated users.",
)
def list_departments(
    response: Response,
    skip: int = Query(0, ge=0, description="Number of departments to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of departments to return"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[DepartmentResponse]:
    departments, total_count = service.list_departments(db, skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(total_count)
    return [DepartmentResponse.model_validate(dept) for dept in departments]


@router.get(
    "/{dept_id}",
    response_model=DepartmentResponse,
    summary="Get department by ID",
    description="Retrieve a single department by its primary key. Accessible to all authenticated users.",
)
def get_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DepartmentResponse:
    try:
        dept = service.get_department(db, dept_id)
        return DepartmentResponse.model_validate(dept)
    except service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department",
    description="Create a new department. Restricted to HR_MANAGER and ADMIN roles.",
)
def create_department(
    payload: DepartmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_roles(["HR_MANAGER", "ADMIN"])
    ),
) -> DepartmentResponse:
    client_ip = request.client.host if request.client else None
    try:
        dept = service.create_department(
            db=db,
            department_in=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return DepartmentResponse.model_validate(dept)
    except service.DepartmentAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.put(
    "/{dept_id}",
    response_model=DepartmentResponse,
    summary="Update department",
    description="Update an existing department. Restricted to HR_MANAGER and ADMIN roles.",
)
def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_roles(["HR_MANAGER", "ADMIN"])
    ),
) -> DepartmentResponse:
    client_ip = request.client.host if request.client else None
    try:
        dept = service.update_department(
            db=db,
            dept_id=dept_id,
            department_in=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return DepartmentResponse.model_validate(dept)
    except service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.DepartmentAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
