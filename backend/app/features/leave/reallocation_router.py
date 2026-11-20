"""Leave-induced task reallocation router (US-14, US-19, S4-BE-5)."""
from datetime import date
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.features.leave.reallocation_service import (
    LeaveReallocationService,
    ReallocationValidationError,
)
from app.features.leave.schemas import (
    TaskReallocationBatchIn,
    TaskReallocationBatchOut,
)
from app.models.user_account import UserAccount

router = APIRouter()


def get_today() -> date:
    """Return today's date; injectable for testing."""
    return date.today()


@router.post(
    "/requests/{id}/reallocate-tasks",
    response_model=TaskReallocationBatchOut,
    status_code=status.HTTP_200_OK,
    summary="Batch reallocate tasks for a leave request (US-14, US-19)",
)
def reallocate_tasks(
    id: int,
    payload: TaskReallocationBatchIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
    today: date = Depends(get_today),
):
    """
    Batch reallocate tasks belonging to a leave applicant during their leave.
    Allowed roles: TEAM_LEAD, PM, ADMIN.
    """
    ip_address = request.client.host if request.client else None
    try:
        return LeaveReallocationService.reallocate_tasks(
            db=db,
            leave_id=id,
            batch=payload,
            current_user=current_user,
            ip_address=ip_address,
            today=today,
        )
    except ReallocationValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "task_id": exc.task_id},
        )
