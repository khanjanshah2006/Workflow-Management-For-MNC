"""Leave-induced task reallocation router (US-14, US-19, S4-BE-5)."""
from datetime import date
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
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
) -> TaskReallocationBatchOut:
    """Batch reallocate tasks belonging to a leave applicant during their leave."""
    raise NotImplementedError()
