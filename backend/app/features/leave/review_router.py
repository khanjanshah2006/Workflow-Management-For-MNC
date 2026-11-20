"""Leave review queue and decision endpoints (S4-BE-4)."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.features.leave.review_service import LeaveReviewService
from app.features.leave.schemas import (
    LeaveApprovalPayload,
    LeaveRejectionPayload,
    LeaveRequestOut,
    PendingLeaveQueueResponse,
)
from app.models.enums import LeaveStatus
from app.models.user_account import UserAccount

router = APIRouter()


def _parse_status_filter(value: str) -> Optional[LeaveStatus]:
    normalized = value.strip().upper()
    if normalized == "ALL":
        return None
    try:
        return LeaveStatus(normalized)
    except ValueError as exc:
        allowed = ", ".join([item.value for item in LeaveStatus] + ["ALL"])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {allowed}",
        ) from exc


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


@router.put(
    "/requests/{id}/approve",
    response_model=LeaveRequestOut,
    summary="Approve a pending leave request",
)
def approve_leave_request(
    id: int,
    payload: LeaveApprovalPayload = Body(default=LeaveApprovalPayload()),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> LeaveRequestOut:
    return LeaveReviewService.approve(
        db=db,
        leave_id=id,
        current_user=current_user,
        review_remarks=payload.review_remarks,
    )


@router.put(
    "/requests/{id}/reject",
    response_model=LeaveRequestOut,
    summary="Reject a pending leave request",
)
def reject_leave_request(
    id: int,
    payload: LeaveRejectionPayload,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> LeaveRequestOut:
    return LeaveReviewService.reject(
        db=db,
        leave_id=id,
        current_user=current_user,
        review_remarks=payload.review_remarks,
    )
