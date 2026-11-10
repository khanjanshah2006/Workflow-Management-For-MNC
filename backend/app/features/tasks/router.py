from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.features.tasks.schemas import TaskAssignRequest, TaskResponse
from app.features.tasks.service import (
    AssigneeNotEligibleError,
    AssigneeNotFoundError,
    TaskAssignmentForbiddenError,
    TaskNotFoundError,
    TaskService,
)
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.put(
    "/{id}/assign",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign task to a team member (US-09)",
    description="Assigns a task to an employee in the task's assigned team. Triggers a real-time notification to the assignee and records an audit log.",
)
def assign_task(
    id: int,
    payload: TaskAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> TaskResponse:
    client_ip = request.client.host if request.client else None
    try:
        return TaskService.assign_task(
            db=db,
            task_id=id,
            payload=payload,
            current_user=current_user,
            ip_address=client_ip,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssigneeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssigneeNotEligibleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TaskAssignmentForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
