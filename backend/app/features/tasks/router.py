from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.tasks.comments import TaskCommentService
from app.features.tasks.schemas import (
    TaskAssignRequest,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskProgressResponse,
    TaskProgressUpdateSchema,
    TaskReassignRequest,
    TaskResponse,
    TaskSubmissionResponse,
)
from app.features.tasks.service import (
    AssigneeNotEligibleError,
    AssigneeNotFoundError,
    InvalidReassignmentReasonError,
    SameAssigneeError,
    TaskAssignmentForbiddenError,
    TaskNotFoundError,
    TaskProgressService,
    TaskService,
    TaskSubmissionService,
)
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


# ==========================================
# Task Assignment & Reassignment (US-09, US-14)
# ==========================================

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


@router.put(
    "/{id}/reassign",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Reassign task to another team member (US-14)",
    description="Reassigns an active task to another team member with mandatory business reason. Triggers dual notifications to new and previous assignees, and writes an audit log.",
)
def reassign_task(
    id: int,
    payload: TaskReassignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> TaskResponse:
    client_ip = request.client.host if request.client else None
    try:
        return TaskService.reassign_task(
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
    except SameAssigneeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssigneeNotEligibleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidReassignmentReasonError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except TaskAssignmentForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


# ==========================================
# Task Deliverables Submission (US-11)
# ==========================================

@router.post(
    "/{id}/comments",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a task comment (US-33)",
    description="Adds a chronological task thread comment and notifies the task counterpart.",
)
def create_task_comment(
    id: int,
    payload: TaskCommentCreate,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "PM", "ADMIN", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db),
) -> TaskCommentResponse:
    return TaskCommentService.create_comment(
        db=db,
        task_id=id,
        content=payload.content,
        current_user=current_user,
    )


@router.get(
    "/{id}/comments",
    response_model=List[TaskCommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List task comments chronologically (US-33)",
    description="Returns the task discussion thread with author names, role badges, and timestamps.",
)
def get_task_comments(
    id: int,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "PM", "ADMIN", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db),
) -> List[TaskCommentResponse]:
    return TaskCommentService.list_comments(db=db, task_id=id, current_user=current_user)


@router.post(
    "/{id}/submit",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit task deliverable for review (US-11)",
    description="Allows an assigned employee to submit remarks and attach deliverables. Transitions task status to IN_REVIEW and notifies the Team Lead.",
)
async def submit_task(
    id: int,
    request: Request,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE"])),
    db: Session = Depends(get_db),
) -> TaskSubmissionResponse:
    """
    Employee endpoint to submit a completed task.
    Supports multipart/form-data (with file attachment and remarks) or application/json.
    """
    content_type = request.headers.get("content-type", "").lower()
    remarks_str: str = ""
    file_obj: Optional[UploadFile] = None
    file_bytes: Optional[bytes] = None
    file_name_val: Optional[str] = None
    file_url_val: Optional[str] = None
    file_size_val: Optional[int] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        remarks_str = str(form.get("remarks") or "")
        raw_file = form.get("file")
        if isinstance(raw_file, UploadFile):
            file_obj = raw_file
            file_name_val = raw_file.filename
        elif hasattr(raw_file, "filename"):
            file_obj = raw_file
            file_name_val = getattr(raw_file, "filename", None)
    elif "application/json" in content_type:
        try:
            body = await request.json()
            remarks_str = body.get("remarks", "")
            file_url_val = body.get("file_url")
            file_name_val = body.get("file_name")
            file_size_val = body.get("file_size_bytes")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload provided.",
            )
    else:
        # Fallback for mixed or unspecified content-types
        try:
            body = await request.json()
            remarks_str = body.get("remarks", "")
            file_url_val = body.get("file_url")
            file_name_val = body.get("file_name")
            file_size_val = body.get("file_size_bytes")
        except Exception:
            form = await request.form()
            remarks_str = str(form.get("remarks") or "")
            raw_file = form.get("file")
            if isinstance(raw_file, UploadFile):
                file_obj = raw_file
                file_name_val = raw_file.filename

    ip_address = request.client.host if request.client else None

    submission = TaskSubmissionService.submit_task(
        db=db,
        task_id=id,
        remarks=remarks_str,
        current_user=current_user,
        file=file_obj,
        file_bytes=file_bytes,
        file_name=file_name_val,
        file_url=file_url_val,
        file_size_bytes=file_size_val,
        ip_address=ip_address,
    )
    return submission


@router.get(
    "/{id}/submissions",
    response_model=List[TaskSubmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get task submissions chronological list (US-11)",
    description="Returns chronological list of all submissions for this task.",
)
def get_task_submissions(
    id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TaskSubmissionResponse]:
    """
    Retrieve all submissions recorded for the specified task in chronological order.
    Enforces ordinary employee isolation: employees may only see submissions for their own tasks.
    """
    return TaskSubmissionService.get_task_submissions(
        db=db,
        task_id=id,
        current_user=current_user,
    )


@router.put(
    "/{id}/progress",
    response_model=TaskProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Update task progress and blocker status (US-10)",
    description=(
        "Allows assigned employees or the Team Lead to update task status (IN_PROGRESS, BLOCKED), "
        "update completion percentage (0-99%), and record blocker explanations. "
        "Flagging as BLOCKED triggers an automatic notification to the Team Lead."
    ),
)
def update_task_progress(
    id: int,
    payload: TaskProgressUpdateSchema,
    request: Request,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "TEAM_LEAD", "ADMIN"])),
    db: Session = Depends(get_db),
) -> TaskProgressResponse:
    """
    Update progress percentage (0-99) or mark task as BLOCKED (US-10).
    - Status == 'BLOCKED' requires blocker_reason (min 5 chars) -> 422
    - Progress == 100% is rejected -> 400 (must use /submit review flow)
    - Non-assigned employees rejected -> 403
    - Dispatches TASK_BLOCKED notification to Team Lead when blocked.
    """
    ip_address = request.client.host if request.client else None
    task = TaskProgressService.update_progress(
        db=db,
        task_id=id,
        payload=payload,
        current_user=current_user,
        ip_address=ip_address,
    )
    return task

