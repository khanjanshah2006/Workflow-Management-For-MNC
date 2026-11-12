from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.tasks.schemas import (
    PaginatedTasksResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskSubmissionResponse,
    TaskSummaryResponse,
)
from app.features.tasks.comments import TaskCommentService
from app.features.tasks.service import TaskService, TaskSubmissionService
from app.models.enums import PriorityLevel, TaskStatus
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])
project_tasks_router = APIRouter(prefix="/api/v1/projects", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task (US-09)",
    description="Creates a task in TODO status with progress_pct=0 and rejection_count=0. Allowed for Team Lead, PM, and Admin.",
)
def create_task(
    payload: TaskCreate,
    request: Request,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDetailResponse:
    ip_address = request.client.host if request.client else None
    return TaskService.create_task(
        db=db,
        payload=payload,
        actor=current_user,
        ip_address=ip_address,
    )


@router.get(
    "/my-tasks",
    response_model=PaginatedTasksResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks assigned to the current user (US-32)",
    description="Returns paginated tasks strictly assigned to the authenticated user's employee record.",
)
def get_my_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority: Optional[PriorityLevel] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedTasksResponse:
    items, total = TaskService.list_my_tasks(
        db=db,
        actor=current_user,
        status_filter=status_filter,
        priority_filter=priority,
        page=page,
        limit=limit,
    )
    return PaginatedTasksResponse(
        items=[TaskSummaryResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get full task details (US-32)",
    description="Returns complete task record including project name, milestone title, creator, and assignee details.",
)
def get_task_detail(
    id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDetailResponse:
    return TaskService.get_task(db=db, task_id=id)


@project_tasks_router.get(
    "/{project_id}/tasks",
    response_model=PaginatedTasksResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks for a project (US-32)",
    description="Lists all tasks for a project, filterable by team_id, milestone_id, and status.",
)
def get_project_tasks(
    project_id: int,
    team_id: Optional[int] = Query(None, ge=1),
    milestone_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedTasksResponse:
    items, total = TaskService.list_project_tasks(
        db=db,
        project_id=project_id,
        team_id=team_id,
        milestone_id=milestone_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return PaginatedTasksResponse(
        items=[TaskSummaryResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        limit=limit,
    )


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
