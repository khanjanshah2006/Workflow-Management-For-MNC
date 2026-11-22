"""
Router for Executive Dashboard & Oversight (US-24, S7).

Prefix: /api/v1/executive
Tags:   Executive

All endpoints are strictly read-only and restricted to MNC_EXECUTIVE, ADMIN,
and SYSTEM_ADMIN roles. Unauthenticated requests receive 401; unauthorized roles receive 403.
"""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.executive.reports import ExecutiveReportService
from app.features.executive.schemas import (
    ExecutiveDepartmentDrilldownResponse,
    ExecutiveOverviewResponse,
    ExecutiveReportCreateRequest,
    ExecutiveReportResponse,
    PaginatedExecutiveReportsResponse,
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


# ------------------------------------------------------------------
# Executive Management Reports Endpoints (US-25, S7-BE-2)
# ------------------------------------------------------------------

@router.post(
    "/reports/generate",
    response_model=ExecutiveReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate executive management report (US-25)",
    description=(
        "Generates a period-bounded executive management report in PDF or CSV format. "
        "Period range must be <= 366 days and start date cannot be in the future. "
        "Persists the report file and records an EXPORT audit log."
    ),
)
def generate_executive_report(
    payload: ExecutiveReportCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> ExecutiveReportResponse:
    """Generate and persist an executive management report (PDF or CSV)."""
    ip_address = request.client.host if request.client else None
    return ExecutiveReportService.generate_report(
        db=db,
        payload=payload,
        current_user=current_user,
        ip_address=ip_address,
    )


@router.get(
    "/reports",
    response_model=PaginatedExecutiveReportsResponse,
    status_code=status.HTTP_200_OK,
    summary="List executive management reports history (US-25)",
    description=(
        "Returns chronological list of previously generated executive management reports "
        "(newest first) with pagination metadata. Accessible by MNC_EXECUTIVE, ADMIN, and SYSTEM_ADMIN."
    ),
)
def list_executive_reports(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> PaginatedExecutiveReportsResponse:
    """List historical executive reports with pagination."""
    return ExecutiveReportService.list_reports(db=db, page=page, limit=limit)


@router.get(
    "/reports/{id}",
    response_model=ExecutiveReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get executive management report metadata (US-25)",
    description="Returns metadata and download link for a specific generated report. Returns 404 if missing.",
)
def get_executive_report(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> ExecutiveReportResponse:
    """Retrieve metadata for a single executive report."""
    return ExecutiveReportService.get_report_by_id(db=db, report_id=id)


@router.get(
    "/reports/{id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download executive management report file (US-25)",
    description=(
        "Streams the generated report file (PDF or CSV) with appropriate Content-Type "
        "and Content-Disposition headers. Returns 404 if the report or file does not exist."
    ),
)
def download_executive_report(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(executive_guard),
) -> Response:
    """Download the generated report file."""
    return ExecutiveReportService.download_report(db=db, report_id=id)

