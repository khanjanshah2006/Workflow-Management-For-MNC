"""
Router for Executive Dashboard & Oversight (US-24, S7).

Prefix: /api/v1/executive
Tags:   Executive

All endpoints are strictly read-only and restricted to MNC_EXECUTIVE, ADMIN,
and SYSTEM_ADMIN roles. Unauthenticated requests receive 401; unauthorized roles receive 403.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.executive.schemas import (
    ExecutiveDepartmentDrilldownResponse,
    ExecutiveOverviewResponse,
)
from app.features.executive.service import ExecutiveService
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/executive", tags=["Executive"])

# RBAC guard: MNC_EXECUTIVE, ADMIN, and SYSTEM_ADMIN
executive_guard = require_role(["MNC_EXECUTIVE", "ADMIN", "SYSTEM_ADMIN"])


@router.get(
    "/dashboard",
    response_model=ExecutiveOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get executive dashboard overview (US-24)",
    description=(
        "Returns high-level organizational KPIs: project status distribution, "
        "delayed projects, overall milestone velocity, task KPIs, total headcount, "
        "and department summaries with milestone velocity. Read-only."
    ),
)
def get_executive_dashboard(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> ExecutiveOverviewResponse:
    """Retrieve the executive dashboard overview."""
    return ExecutiveService.get_dashboard_overview(db=db)


@router.get(
    "/dashboard/departments/{id}",
    response_model=ExecutiveDepartmentDrilldownResponse,
    status_code=status.HTTP_200_OK,
    summary="Get department executive drilldown (US-24)",
    description=(
        "Returns granular project progress, teams, and resource allocation "
        "for a specific department. Returns 404 if department does not exist. Read-only."
    ),
)
def get_department_drilldown(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> ExecutiveDepartmentDrilldownResponse:
    """Retrieve granular department metrics, projects, teams, and staffing."""
    return ExecutiveService.get_department_drilldown(db=db, dept_id=id)
