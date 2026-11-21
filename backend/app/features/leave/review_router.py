"""Leave conflict reporting and review queue/decision endpoints (S4)."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.review_service import LeaveReviewService
from app.features.leave.schemas import (
    LeaveApprovalPayload,
    LeaveConflictReportOut,
    LeaveRejectionPayload,
    LeaveRequestOut,
    PendingLeaveQueueResponse,
)
from app.features.leave.service import LeaveService
from app.models.enums import LeaveStatus
from app.models.user_account import UserAccount

router = APIRouter()

ALLOWED_REVIEWER_ROLES = ["TEAM_LEAD", "PM", "HR", "ADMIN", "SYSTEM_ADMIN"]


def _parse_status_filter(value: str) -> Optional[LeaveStatus]:
    normalized = value.strip().upper()
    if normalized == "ALL":
        return None
    try:
        return LeaveStatus(normalized)
    except ValueError as exc:
        allowed = ", ".join([item.value for item in LeaveStatus] + ["ALL"])
        raise HTTPException(status_code=422, detail=f"status must be one of: {allowed}") from exc


@router.get(
    "/requests/pending",
    response_model=PendingLeaveQueueResponse,
    summary="List leave requests for review",
)
def get_pending_leave_requests(
    status_filter: str = Query("PENDING", alias="status", min_length=1, max_length=16),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> PendingLeaveQueueResponse:
    return LeaveReviewService.list_pending_requests(
        db=db,
        current_user=current_user,
        status_filter=_parse_status_filter(status_filter),
        page=page,
        limit=limit,
    )


@router.put("/requests/{id}/approve", response_model=LeaveRequestOut, summary="Approve a pending leave request")
def approve_leave_request(
    id: int,
    payload: LeaveApprovalPayload = Body(default=LeaveApprovalPayload()),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> LeaveRequestOut:
    return LeaveReviewService.approve(
        db=db, leave_id=id, current_user=current_user, review_remarks=payload.review_remarks
    )


@router.put("/requests/{id}/reject", response_model=LeaveRequestOut, summary="Reject a pending leave request")
def reject_leave_request(
    id: int,
    payload: LeaveRejectionPayload,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> LeaveRequestOut:
    return LeaveReviewService.reject(
        db=db, leave_id=id, current_user=current_user, review_remarks=payload.review_remarks
    )


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
