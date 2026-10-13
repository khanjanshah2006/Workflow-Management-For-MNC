from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.profile.schemas import (
    ProfileResponse,
    ProfileUpdateRequest,
    SkillResponse,
)
from app.features.profile.service import ProfileService

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])


@router.get(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current employee profile (US-03)",
    description="Retrieve the authenticated employee's full organizational profile, department, and manager/lead details.",
)
def get_my_profile(
    current_user: UserAccount = Depends(require_role(["EMPLOYEE"])),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """
    Fetch the currently authenticated employee's profile.
    Restricted to users with EMPLOYEE role.
    """
    return ProfileService.get_my_profile(db=db, current_user=current_user)


@router.put(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current employee contact details (US-03)",
    description="Update permitted contact fields (phone, address, emergency contact). All changes are recorded in the audit trail.",
)
def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE"])),
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
    current_user: UserAccount = Depends(require_role(["EMPLOYEE"])),
    db: Session = Depends(get_db),
) -> List[SkillResponse]:
    """
    Retrieve all assigned skills and proficiency ratings for the logged-in employee.
    Restricted to users with EMPLOYEE role.
    """
    return ProfileService.get_my_skills(db=db, current_user=current_user)
