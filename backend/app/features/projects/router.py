from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.projects.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectAssignmentCreate,
    ProjectAssignmentResponse,
    TeamCreate,
    TeamResponse,
    TeamMemberAdd,
    TeamMemberResponse,
)
from app.features.projects.service import (
    ProjectService,
    ProjectNotFoundError,
    ProjectCodeAlreadyExistsError,
    ClientNotFoundError,
    ProjectManagerNotFoundError,
    EmployeeNotFoundError,
    EmployeeNotAssignedToProjectError,
    EmployeeAlreadyAssignedError,
    TeamNotFoundError,
    TeamMemberAlreadyExistsError,
    InvalidDateRangeError,
    UnauthorizedProjectAccessError,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

# Role guard for project leadership
pm_or_admin_guard = require_role(["PM", "PROJECT_MANAGER", "ADMIN"])


# ==========================================
# Project Endpoints (US-06)
# ==========================================

@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project (US-06)",
    description="Allows Project Managers and Admins to create a project record with dates, priority, client, and PM assignment.",
)
def create_project(
    payload: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(pm_or_admin_guard),
) -> ProjectResponse:
    client_ip = request.client.host if request.client else None
    try:
        return ProjectService.create_project(
            db=db,
            payload=payload,
            current_user=current_user,
            ip_address=client_ip,
        )
    except InvalidDateRangeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectManagerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectCodeAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List projects (US-06)",
    description="List projects scoped to user role (PM sees managed projects; Employee sees assigned projects; Admin sees all).",
)
def list_projects(
    response: Response,
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max projects per page"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[ProjectResponse]:
    projects, total_count = ProjectService.list_projects(
        db=db, current_user=current_user, skip=skip, limit=limit
    )
    response.headers["X-Total-Count"] = str(total_count)
    return projects


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details (US-06)",
    description="Retrieve a single project by primary key ID.",
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ProjectResponse:
    try:
        return ProjectService.get_project(db=db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ==========================================
# Project Staffing Endpoints (US-07)
# ==========================================

@router.post(
    "/{project_id}/assign",
    response_model=ProjectAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an employee to a project (US-07)",
    description="Allocates an employee to the project roster. Restricted to the project's PM and Admins.",
)
def assign_employee_to_project(
    project_id: int,
    payload: ProjectAssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(pm_or_admin_guard),
) -> ProjectAssignmentResponse:
    client_ip = request.client.host if request.client else None
    try:
        return ProjectService.assign_employee(
            db=db,
            project_id=project_id,
            payload=payload,
            current_user=current_user,
            ip_address=client_ip,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedProjectAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except EmployeeAlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/{project_id}/assignments",
    response_model=List[ProjectAssignmentResponse],
    summary="List project roster assignments (US-07)",
    description="Retrieve all employees allocated to a project.",
)
def list_project_assignments(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[ProjectAssignmentResponse]:
    try:
        return ProjectService.list_assignments(db=db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ==========================================
# Team Endpoints (US-07)
# ==========================================

@router.post(
    "/{project_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a team inside a project (US-07)",
    description="Creates a designated team under a project. Restricted to managing PM and Admins.",
)
def create_project_team(
    project_id: int,
    payload: TeamCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(pm_or_admin_guard),
) -> TeamResponse:
    client_ip = request.client.host if request.client else None
    try:
        return ProjectService.create_team(
            db=db,
            project_id=project_id,
            payload=payload,
            current_user=current_user,
            ip_address=client_ip,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmployeeNotAssignedToProjectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnauthorizedProjectAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/{project_id}/teams",
    response_model=List[TeamResponse],
    summary="List teams in a project (US-07)",
    description="Retrieve all teams formed within a project.",
)
def list_project_teams(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[TeamResponse]:
    try:
        return ProjectService.list_teams(db=db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ==========================================
# Team Membership Endpoints (US-07)
# ==========================================

@router.post(
    "/{project_id}/teams/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an allocated employee to a team (US-07)",
    description="Enforces strict domain rule: Employee MUST hold active project assignment first, returning 400 if unassigned.",
)
def add_team_member(
    project_id: int,
    team_id: int,
    payload: TeamMemberAdd,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(pm_or_admin_guard),
) -> TeamMemberResponse:
    client_ip = request.client.host if request.client else None
    try:
        return ProjectService.add_team_member(
            db=db,
            project_id=project_id,
            team_id=team_id,
            payload=payload,
            current_user=current_user,
            ip_address=client_ip,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmployeeNotAssignedToProjectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TeamMemberAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnauthorizedProjectAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/{project_id}/teams/{team_id}/members",
    response_model=List[TeamMemberResponse],
    summary="List members in a team (US-07)",
    description="Retrieve all employees currently belonging to this team.",
)
def list_team_members(
    project_id: int,
    team_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[TeamMemberResponse]:
    try:
        return ProjectService.list_team_members(db=db, project_id=project_id, team_id=team_id)
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
