"""Leave conflicts (S4-BE-3) and review queue / decisions (S4-BE-4)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.schemas import LeaveConflictReportOut
from app.features.leave.service import LeaveService
from app.models.user_account import UserAccount

router = APIRouter()

ALLOWED_REVIEWER_ROLES = [
    "TEAM_LEAD",
    "PM",
    "HR",
    "ADMIN",
    "SYSTEM_ADMIN",
]


@router.get(
    "/requests/{id}/conflicts",
    response_model=LeaveConflictReportOut,
    status_code=status.HTTP_200_OK,
    summary="Get leave conflict report (US-17)",
    description="Evaluates conflicting tasks, milestone impacts, and teammate reassignment availability for a leave request.",
)
def get_leave_conflicts(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(ALLOWED_REVIEWER_ROLES)),
) -> LeaveConflictReportOut:
    """Return conflict report for the specified leave request."""
    return LeaveService.get_leave_conflicts(db=db, leave_id=id, current_user=current_user)
