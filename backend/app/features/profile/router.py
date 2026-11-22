from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core import roles
from app.core.rbac import require_role
from app.models.enums import SkillChangeStatus
from app.models.user_account import UserAccount
from app.features.profile.schemas import (
    ProfileResponse,
    ProfileUpdateRequest,
    SkillResponse,
    SkillChangeRequestCreate,
    SkillChangeDecisionIn,
    SkillChangeRequestOut,
    PaginatedSkillChangeRequestsOut,
)
from app.features.profile.service import ProfileService

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])
skill_requests_router = APIRouter(prefix="/api/v1/skill-requests", tags=["Skill Requests"])

SKILL_REVIEWER_ROLES = (
    roles.HR,
    roles.TEAM_LEAD,
    roles.ADMIN,
    roles.SYSTEM_ADMIN,
)
@router.get(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current employee profile (US-03)",
    description="Retrieve the authenticated employee's full organizational profile, department, and manager/lead details.",
)
def get_my_profile(
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """
    Fetch the currently authenticated employee's profile.
    Restricted to internal employee accounts.
    """
    return ProfileService.get_my_profile(db=db, current_user=current_user)


@router.put(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current employee contact details (US-03)",
    description="Update permitted contact fields (phone, address, emergency contact, bio). All changes are recorded in the audit trail.",
)
def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """
    Update permitted personal contact details for the logged-in employee.
    Enforces RBAC and triggers an audit log entry on completion.
    """
    ip_address = request.client.host if request.client else None
    return ProfileService.update_my_profile(
        db=db,
        payload=payload,
        current_user=current_user,
        ip_address=ip_address,
    )


@router.get(
    "/me/skills",
    response_model=List[SkillResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current employee assigned skills (US-03)",
    description="Retrieve technical and domain skills assigned to the authenticated employee with proficiency levels and experience.",
)
def get_my_skills(
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
    db: Session = Depends(get_db),
) -> List[SkillResponse]:
    """
    Retrieve all assigned skills and proficiency ratings for the logged-in employee.
    Restricted to internal employee accounts.
    """
    return ProfileService.get_my_skills(db=db, current_user=current_user)


# ── US-34 Skill Proposals Endpoints (Employee Self-Service) ──────────────────

@router.post(
    "/me/skill-requests",
    response_model=SkillChangeRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Propose skill change (US-34)",
    description="Propose addition, update, or removal of a skill rating. Triggers notifications and audit trail.",
)
def propose_skill_change(
    payload: SkillChangeRequestCreate,
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
    db: Session = Depends(get_db),
) -> SkillChangeRequestOut:
    """
    Submit a skill proposal (ADD, UPDATE, or REMOVE).
    Rejects duplicate pending proposals for the same skill with 409 Conflict.
    """
    return ProfileService.propose_skill_change(db=db, current_user=current_user, data=payload)


@router.get(
    "/me/skill-requests",
    response_model=List[SkillChangeRequestOut],
    status_code=status.HTTP_200_OK,
    summary="List current employee's skill proposals (US-34)",
    description="Retrieve all skill change requests submitted by the current employee, newest first.",
)
def list_my_skill_requests(
    current_user: UserAccount = Depends(require_role(roles.INTERNAL)),
    db: Session = Depends(get_db),
) -> List[SkillChangeRequestOut]:
    """Fetch all skill proposals submitted by the authenticated employee."""
    return ProfileService.list_my_skill_requests(db=db, current_user=current_user)


# ── US-34 Skill Review Queue Endpoints (HR & Team Leads) ─────────────────────

@skill_requests_router.get(
    "",
    response_model=PaginatedSkillChangeRequestsOut,
    status_code=status.HTTP_200_OK,
    summary="List skill proposals queue (US-34)",
    description="HR and Admins see all requests; Team Leads see requests from their led team members. Paginated.",
)
def list_skill_requests_queue(
    status: Optional[SkillChangeStatus] = Query(None, description="Optional status filter (e.g. PENDING)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserAccount = Depends(require_role(SKILL_REVIEWER_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedSkillChangeRequestsOut:
    """
    Retrieve paginated skill proposals for review. Scoped by role:
    HR/Admin see organization-wide; Team Leads see only members of active teams they lead.
    """
    return ProfileService.list_skill_requests_queue(
        db=db,
        current_user=current_user,
        status_filter=status,
        page=page,
        limit=limit,
    )


@skill_requests_router.put(
    "/{id}/approve",
    response_model=SkillChangeRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Approve skill change request (US-34)",
    description="Approve a pending skill change request and apply changes to employee skills. Authorized for HR or requester's Team Lead.",
)
def approve_skill_request(
    id: int,
    payload: SkillChangeDecisionIn = SkillChangeDecisionIn(),
    current_user: UserAccount = Depends(require_role(SKILL_REVIEWER_ROLES)),
    db: Session = Depends(get_db),
) -> SkillChangeRequestOut:
    """
    Approve a skill change proposal.
    Enforces authorization (HR or Team Lead), idempotency (409 if already decided),
    updates employee skills, logs audit trail, and notifies requester.
    """
    return ProfileService.approve_skill_request(
        db=db,
        current_user=current_user,
        request_id=id,
        payload=payload,
    )


@skill_requests_router.put(
    "/{id}/reject",
    response_model=SkillChangeRequestOut,
    status_code=status.HTTP_200_OK,
    summary="Reject skill change request (US-34)",
    description="Reject a pending skill change request with mandatory remarks. Authorized for HR or requester's Team Lead.",
)
def reject_skill_request(
    id: int,
    payload: SkillChangeDecisionIn,
    current_user: UserAccount = Depends(require_role(SKILL_REVIEWER_ROLES)),
    db: Session = Depends(get_db),
) -> SkillChangeRequestOut:
    """
    Reject a skill change proposal.
    Remarks are mandatory (400 if empty).
    Enforces authorization, idempotency (409), logs audit trail, and notifies requester.
    """
    return ProfileService.reject_skill_request(
        db=db,
        current_user=current_user,
        request_id=id,
        payload=payload,
    )
