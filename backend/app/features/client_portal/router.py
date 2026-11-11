"""
Router for the Client Portal feature (US-20, US-21).

Prefix: /api/v1/client
Tags:   Client Portal

All endpoints are restricted to the CLIENT role.  Data is strictly scoped
to the authenticated client's own contracted projects and milestones.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.client_portal.schemas import (
    ClientMilestoneResponse,
    ClientProjectSummaryResponse,
)
from app.features.client_portal.service import ClientPortalService
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/client", tags=["Client Portal"])

# RBAC guard – only CLIENT role may access these endpoints
client_guard = require_role(["CLIENT"])


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

