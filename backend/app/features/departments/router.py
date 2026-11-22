from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.departments import service
from app.core import roles
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    TeamMemberOut,
    DepartmentTeamCreate,
    DepartmentTeamUpdate,
    DepartmentTeamMemberAdd,
    DepartmentTeamResponse,
    DepartmentTeamListItem,
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
    description="Create a new department. Restricted to HR and ADMIN roles.",
)
def create_department(
    payload: DepartmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
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
    description="Update an existing department. Restricted to HR and ADMIN roles.",
)
def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
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


# ==========================================
# Department Team Endpoints (US-05, Issue #141)
# ==========================================


@router.post(
    "/{dept_id}/teams",
    response_model=DepartmentTeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department team (US-05)",
    description="Creates a new team under the specified department with designated lead and initial members. Restricted to HR and ADMIN roles.",
)
def create_department_team(
    dept_id: int,
    payload: DepartmentTeamCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
    ),
) -> DepartmentTeamResponse:
    client_ip = request.client.host if request.client else None
    try:
        team, lead, members = service.create_department_team(
            db=db,
            dept_id=dept_id,
            team_in=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return DepartmentTeamResponse(
            team_id=team.team_id,
            dept_id=team.dept_id,
            project_id=team.project_id,
            name=team.name,
            description=team.description,
            lead_emp_id=team.lead_emp_id,
            lead_name=lead.full_name if lead else None,
            status=team.status,
            created_at=team.created_at,
            member_count=len(members),
            members=[
                TeamMemberOut(
                    employee_id=m.emp_id,
                    emp_code=m.emp_code,
                    full_name=m.full_name,
                    email=m.email,
                    designation=m.designation,
                )
                for m in members
            ],
        )
    except (service.DepartmentNotFoundError, service.EmployeeNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.EmployeeInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except service.TeamNameAlreadyExistsInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{dept_id}/teams",
    response_model=list[DepartmentTeamListItem],
    summary="List department teams (US-05)",
    description="Retrieve teams in a department with lead name and member count. Defaults to ACTIVE teams only; ?include_disbanded=true includes disbanded teams.",
)
def list_department_teams(
    dept_id: int,
    include_disbanded: bool = Query(False, description="Whether to include disbanded teams"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
) -> list[DepartmentTeamListItem]:
    try:
        items = service.list_department_teams(
            db=db,
            dept_id=dept_id,
            include_disbanded=include_disbanded,
        )
        return [
            DepartmentTeamListItem(
                team_id=t.team_id,
                dept_id=t.dept_id,
                project_id=t.project_id,
                name=t.name,
                description=t.description,
                lead_emp_id=t.lead_emp_id,
                lead_name=lead_name,
                status=t.status,
                created_at=t.created_at,
                member_count=count,
            )
            for t, lead_name, count in items
        ]
    except service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ==========================================
# Team Endpoints (US-37)
# ==========================================

team_router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])


@team_router.get(
    "/{id}/members",
    response_model=list[TeamMemberOut],
    summary="Get team members roster (US-37)",
    description=(
        "Queries employee joining on team_member where team_id = {id} and status = ACTIVE. "
        "Returns employee_id, emp_code, full_name, email, designation. "
        "Team Leads can query their own assigned team (403 Forbidden for other teams). "
        "HR and SysAdmin can query any team's roster. "
        "Returns empty array cleanly if team has no members assigned."
    ),
    responses={
        200: {"description": "Active team member roster list"},
        401: {"description": "Authentication required"},
        403: {"description": "Forbidden: not authorized to view this team's roster"},
        404: {"description": "Team not found"},
    },
)
def get_team_members(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[TeamMemberOut]:
    try:
        members = service.get_team_members(db, team_id=id, current_user=current_user)
        return [
            TeamMemberOut(
                employee_id=emp.emp_id,
                emp_code=emp.emp_code,
                full_name=emp.full_name,
                email=emp.email,
                designation=emp.designation,
            )
            for emp in members
        ]
    except service.TeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.TeamAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@team_router.get(
    "/{id}/tasks",
    response_model=list[Any],
    summary="Get team tasks (stub) (US-37)",
    description=(
        "Stub returning [] until S3 tasks land. "
        "Team Leads can query their own assigned team (403 Forbidden for other teams). "
        "HR and SysAdmin can query any team."
    ),
    responses={
        200: {"description": "List of tasks (empty array stub)"},
        401: {"description": "Authentication required"},
        403: {"description": "Forbidden: not authorized to view this team"},
        404: {"description": "Team not found"},
    },
)
def get_team_tasks(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[Any]:
    try:
        return service.get_team_tasks(db, team_id=id, current_user=current_user)
    except service.TeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.TeamAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@team_router.put(
    "/{team_id}",
    response_model=DepartmentTeamResponse,
    summary="Update team (US-05, Issue #141)",
    description="Partial update of name, description, lead_emp_id, and status. Restricted to HR and ADMIN roles.",
)
def update_team(
    team_id: int,
    payload: DepartmentTeamUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
    ),
) -> DepartmentTeamResponse:
    client_ip = request.client.host if request.client else None
    try:
        team, lead, members = service.update_team(
            db=db,
            team_id=team_id,
            team_in=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return DepartmentTeamResponse(
            team_id=team.team_id,
            dept_id=team.dept_id,
            project_id=team.project_id,
            name=team.name,
            description=team.description,
            lead_emp_id=team.lead_emp_id,
            lead_name=lead.full_name if lead else None,
            status=team.status,
            created_at=team.created_at,
            member_count=len(members),
            members=[
                TeamMemberOut(
                    employee_id=m.emp_id,
                    emp_code=m.emp_code,
                    full_name=m.full_name,
                    email=m.email,
                    designation=m.designation,
                )
                for m in members
            ],
        )
    except (service.TeamNotFoundError, service.EmployeeNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.EmployeeInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except service.TeamNameAlreadyExistsInDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@team_router.post(
    "/{team_id}/members",
    response_model=DepartmentTeamResponse,
    summary="Add members to team (US-05, Issue #141)",
    description="Idempotently add members to team. Restricted to HR and ADMIN roles.",
)
def add_team_members(
    team_id: int,
    payload: DepartmentTeamMemberAdd,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
    ),
) -> DepartmentTeamResponse:
    client_ip = request.client.host if request.client else None
    try:
        team, lead, members = service.add_team_members(
            db=db,
            team_id=team_id,
            members_in=payload,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return DepartmentTeamResponse(
            team_id=team.team_id,
            dept_id=team.dept_id,
            project_id=team.project_id,
            name=team.name,
            description=team.description,
            lead_emp_id=team.lead_emp_id,
            lead_name=lead.full_name if lead else None,
            status=team.status,
            created_at=team.created_at,
            member_count=len(members),
            members=[
                TeamMemberOut(
                    employee_id=m.emp_id,
                    emp_code=m.emp_code,
                    full_name=m.full_name,
                    email=m.email,
                    designation=m.designation,
                )
                for m in members
            ],
        )
    except (service.TeamNotFoundError, service.EmployeeNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.EmployeeInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@team_router.delete(
    "/{team_id}/members/{emp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from team (US-05, Issue #141)",
    description="Remove employee from team members. Removing lead returns 409 Conflict. Restricted to HR and ADMIN roles.",
)
def remove_team_member(
    team_id: int,
    emp_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(
        require_role((roles.HR, roles.ADMIN))
    ),
) -> Response:
    client_ip = request.client.host if request.client else None
    try:
        service.remove_team_member(
            db=db,
            team_id=team_id,
            emp_id=emp_id,
            actor_account_id=current_user.account_id,
            ip_address=client_ip,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (service.TeamNotFoundError, service.EmployeeNotFoundError, service.TeamMemberNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.CannotRemoveLeadError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


