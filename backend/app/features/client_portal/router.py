"""
Router for the Client Portal feature (US-20, US-21, US-22, US-41, US-42).

Routers exported:
  - ``router`` (prefix ``/api/v1/client``): Client-facing project, milestone,
    report export, deliverable listing, and signoff feedback endpoints.
  - ``project_deliverables_router`` (prefix ``/api/v1/projects``): PM/Admin
    deliverable publishing endpoint.
  - ``project_visibility_router`` (prefix ``/api/v1/projects``): PM/Admin
    client visibility toggle endpoint.
"""

from io import BytesIO
from typing import List

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.client_portal.schemas import (
    ClientMilestoneResponse,
    ClientProjectSummaryResponse,
    ClientVisibilityResponse,
    ClientVisibilityUpdate,
    DeliverableCreateIn,
    DeliverableFeedbackIn,
    DeliverableOut,
)
from app.features.client_portal.service import ClientPortalService
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/client", tags=["Client Portal"])
project_deliverables_router = APIRouter(
    prefix="/api/v1/projects", tags=["Client Portal"]
)
project_visibility_router = APIRouter(
    prefix="/api/v1/projects", tags=["Client Portal"]
)

# RBAC guards
client_guard = require_role(["CLIENT"])
pm_or_admin_guard = require_role(["PM", "ADMIN"])
client_or_pm_guard = require_role(["CLIENT", "PM"])


# ==========================================
# Client Projects Endpoint (US-20)
# ==========================================

@router.get(
    "/projects",
    response_model=List[ClientProjectSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List contracted projects with milestone progress (US-20)",
    description=(
        "Returns every project belonging to the authenticated client with "
        "high-level milestone completion metrics.  Internal employee data, "
        "task assignments, and internal notes are completely redacted."
    ),
)
def list_client_projects(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(client_guard),
) -> List[ClientProjectSummaryResponse]:
    return ClientPortalService.get_client_projects(db, current_user)


# ==========================================
# Client Project Milestones Endpoint (US-21)
# ==========================================

@router.get(
    "/projects/{project_id}/milestones",
    response_model=List[ClientMilestoneResponse],
    status_code=status.HTTP_200_OK,
    summary="View milestones for a contracted project (US-21)",
    description=(
        "Returns delivery milestones for a specific project that belongs "
        "to the authenticated client.  Returns 404 if the project does not "
        "exist or belongs to another client."
    ),
)
def list_project_milestones(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(client_guard),
) -> List[ClientMilestoneResponse]:
    return ClientPortalService.get_project_milestones(db, project_id, current_user)


# ==========================================
# Export Client Project Report PDF (US-41)
# ==========================================

@router.get(
    "/projects/{id}/report/export",
    status_code=status.HTTP_200_OK,
    summary="Export project progress report as PDF (US-41)",
    description=(
        "Generates and streams a downloadable PDF progress report for a project. "
        "Allowed for CLIENT (own projects), PM, and ADMIN. "
        "Masks employee names when is_team_visible_to_client is False."
    ),
)
def export_project_report_pdf(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(["CLIENT", "PM", "ADMIN"])),
) -> StreamingResponse:
    pdf_bytes = ClientPortalService.generate_project_report_pdf(
        db=db,
        project_id=id,
        current_user=current_user,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="Project_Report_{id}.pdf"'
    }
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )


# ==========================================
# Toggle Client Team Visibility (US-42)
# ==========================================

@project_visibility_router.put(
    "/{id}/client-visibility",
    response_model=ClientVisibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle client team visibility for a project (US-42)",
    description="Allows PM or ADMIN to toggle whether team member names are visible in client PDF exports.",
)
def update_project_client_visibility(
    id: int,
    payload: ClientVisibilityUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(["PM", "ADMIN"])),
) -> ClientVisibilityResponse:
    ip_address = request.client.host if request.client else None
    return ClientPortalService.toggle_client_visibility(
        db=db,
        project_id=id,
        is_visible=payload.is_team_visible_to_client,
        actor=current_user,
        ip_address=ip_address,
    )


# ==========================================
# Project Deliverables & Signoff (US-22)
# ==========================================

@project_deliverables_router.post(
    "/{project_id}/deliverables",
    response_model=DeliverableOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a client-facing project deliverable (US-22)",
    description=(
        "Allows assigned Project Managers or Admins to publish a deliverable "
        "for client review and signoff."
    ),
)
def publish_project_deliverable(
    project_id: int,
    payload: DeliverableCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(pm_or_admin_guard),
) -> DeliverableOut:
    client_ip = request.client.host if request.client else None
    return ClientPortalService.publish_deliverable(
        db=db,
        project_id=project_id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.get(
    "/projects/{project_id}/deliverables",
    response_model=List[DeliverableOut],
    status_code=status.HTTP_200_OK,
    summary="List published deliverables for a project (US-22)",
    description=(
        "Returns published deliverables with version history, signoff status, "
        "and client feedback.  Allowed for the owning CLIENT or assigned PM."
    ),
)
def list_project_deliverables(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(client_or_pm_guard),
) -> List[DeliverableOut]:
    return ClientPortalService.list_project_deliverables(
        db=db, project_id=project_id, current_user=current_user
    )


@router.post(
    "/deliverables/{deliverable_id}/feedback",
    response_model=DeliverableOut,
    status_code=status.HTTP_200_OK,
    summary="Submit feedback or formal signoff on a deliverable (US-22)",
    description=(
        "Allows the owning CLIENT to accept a deliverable or request changes "
        "(mandatory comments when requesting changes), notifies the Project "
        "Manager, and writes an audit log entry."
    ),
)
def submit_deliverable_feedback(
    deliverable_id: int,
    payload: DeliverableFeedbackIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(client_guard),
) -> DeliverableOut:
    client_ip = request.client.host if request.client else None
    return ClientPortalService.submit_deliverable_feedback(
        db=db,
        deliverable_id=deliverable_id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )
