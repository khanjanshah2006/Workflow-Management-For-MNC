"""Leave requests and history router (US-16, S4-BE-1)."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.schemas import (
    LeaveRequestCreate,
    LeaveRequestOut,
)
from app.features.leave.service import LeaveService
from app.models.enums import LeaveStatus
from app.models.user_account import UserAccount

router = APIRouter()


def get_today() -> date:
    """Return today's date; injectable for testing."""
    return date.today()


@router.post(
    "/requests",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new leave request (US-16)",
)
def submit_leave_request(
    payload: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
    today: date = Depends(get_today),
) -> LeaveRequestOut:
    """
    Submit a leave request.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    Requires an active employee profile.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return LeaveService.submit_leave_request(
        db=db,
        current_user=current_user,
        data=payload,
        today=today,
    )


@router.get(
    "/requests/my",
    response_model=List[LeaveRequestOut],
    status_code=status.HTTP_200_OK,
    summary="List leave history for current user (US-16)",
)
def get_my_leave_requests(
    status_filter: Optional[LeaveStatus] = Query(None, alias="status", description="Filter by status"),
    year: Optional[int] = Query(None, description="Filter by start date calendar year"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[LeaveRequestOut]:
    """
    Retrieve leave history for the authenticated employee.
    Allowed roles: EMPLOYEE, TEAM_LEAD.
    """
    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return LeaveService.list_my_leave_history(
        db=db,
        current_user=current_user,
        status_filter=status_filter,
        year=year,
        page=page,
        limit=limit,
    )
